import threading
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, Qt

class MprisIntegration(QObject):
    command_requested = pyqtSignal(str)

    def __init__(self, player):
        super().__init__(player)
        self.command_requested.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)
        self.player = player
        self.bus = None
        self.running = False
        
        # We start it in a background thread to avoid blocking the GUI
        # if dbus hangs or takes time.
        self.thread = threading.Thread(target=self._init_mpris, daemon=True)
        self.thread.start()

        # Connect to player signals
        self.player.track_loaded.connect(self._on_track_loaded)
        self.player.state_changed.connect(self._on_state_changed)
        
    @pyqtSlot(str)
    def _dispatch(self, command):
        actions = {"toggle": self.player.toggle_pause,
                   "next": self.player.next_track,
                   "previous": self.player.prev_track}
        actions[command]()

    def _init_mpris(self):
        try:
            import dbus
            import dbus.service
            from dbus.mainloop.glib import DBusGMainLoop
            from gi.repository import GLib

            DBusGMainLoop(set_as_default=True)
            self.bus = dbus.SessionBus()
            
            class MprisPlayer(dbus.service.Object):
                def __init__(self, bus, player_ref, commands):
                    self.player_ref = player_ref
                    self.commands = commands
                    self.path = "/org/mpris/MediaPlayer2"
                    dbus.service.Object.__init__(self, bus, self.path)
                    
                    self.PlaybackStatus = "Stopped"
                    self.Metadata = dbus.Dictionary({}, signature='sv')
                    
                @dbus.service.method("org.freedesktop.DBus.Properties", in_signature='ss', out_signature='v')
                def Get(self, interface, prop):
                    if interface == "org.mpris.MediaPlayer2.Player":
                        if prop == "PlaybackStatus":
                            return dbus.String(self.PlaybackStatus, variant_level=1)
                        elif prop == "Metadata":
                            return dbus.Dictionary(self.Metadata, signature='sv', variant_level=1)
                        elif prop == "CanControl":
                            return dbus.Boolean(True, variant_level=1)
                        elif prop == "CanPause":
                            return dbus.Boolean(True, variant_level=1)
                        elif prop == "CanPlay":
                            return dbus.Boolean(True, variant_level=1)
                        elif prop == "CanGoNext":
                            return dbus.Boolean(True, variant_level=1)
                        elif prop == "CanGoPrevious":
                            return dbus.Boolean(True, variant_level=1)
                    elif interface == "org.mpris.MediaPlayer2":
                        if prop == "DesktopEntry":
                            return dbus.String("music-crow", variant_level=1)
                        elif prop == "Identity":
                            return dbus.String("Music Crow", variant_level=1)
                    return None
                    
                @dbus.service.method("org.freedesktop.DBus.Properties", in_signature='s', out_signature='a{sv}')
                def GetAll(self, interface):
                    if interface == "org.mpris.MediaPlayer2.Player":
                        return dbus.Dictionary({
                            "PlaybackStatus": dbus.String(self.PlaybackStatus, variant_level=0),
                            "Metadata": dbus.Dictionary(self.Metadata, signature='sv', variant_level=0),
                            "CanControl": dbus.Boolean(True, variant_level=0),
                            "CanPause": dbus.Boolean(True, variant_level=0),
                            "CanPlay": dbus.Boolean(True, variant_level=0),
                            "CanGoNext": dbus.Boolean(True, variant_level=0),
                            "CanGoPrevious": dbus.Boolean(True, variant_level=0)
                        }, signature='sv')
                    elif interface == "org.mpris.MediaPlayer2":
                        return dbus.Dictionary({
                            "DesktopEntry": dbus.String("music-crow", variant_level=0),
                            "Identity": dbus.String("Music Crow", variant_level=0)
                        }, signature='sv')
                    return dbus.Dictionary({}, signature='sv')

                @dbus.service.method("org.mpris.MediaPlayer2.Player")
                def PlayPause(self):
                    self.commands.emit("toggle")

                @dbus.service.method("org.mpris.MediaPlayer2.Player")
                def Play(self):
                    if self.player_ref.mpv.pause:
                        self.commands.emit("toggle")

                @dbus.service.method("org.mpris.MediaPlayer2.Player")
                def Pause(self):
                    if not self.player_ref.mpv.pause:
                        self.commands.emit("toggle")

                @dbus.service.method("org.mpris.MediaPlayer2.Player")
                def Next(self):
                    self.commands.emit("next")

                @dbus.service.method("org.mpris.MediaPlayer2.Player")
                def Previous(self):
                    self.commands.emit("previous")
                    
                @dbus.service.signal("org.freedesktop.DBus.Properties", signature='sa{sv}as')
                def PropertiesChanged(self, interface, changed_properties, invalidated_properties):
                    pass

                def update_status(self, is_playing):
                    self.PlaybackStatus = "Playing" if is_playing else "Paused"
                    self.PropertiesChanged("org.mpris.MediaPlayer2.Player", {"PlaybackStatus": self.PlaybackStatus}, [])
                    
                def update_metadata(self, title, artist, art_url):
                    self.Metadata = dbus.Dictionary({
                        "mpris:trackid": dbus.ObjectPath("/org/mpris/MediaPlayer2/TrackList/NoTrack"),
                        "xesam:title": dbus.String(title),
                        "xesam:artist": dbus.Array([dbus.String(artist)], signature='s'),
                        "mpris:artUrl": dbus.String(art_url) if art_url else dbus.String(""),
                    }, signature='sv')
                    self.PropertiesChanged("org.mpris.MediaPlayer2.Player", {"Metadata": self.Metadata}, [])

            name = dbus.service.BusName("org.mpris.MediaPlayer2.musiccrow", self.bus)
            self.mpris_object = MprisPlayer(self.bus, self.player, self.command_requested)
            self.running = True
            
            loop = GLib.MainLoop()
            loop.run()
        except ImportError as e:
            print(f"MPRIS integration disabled: dependencies not met ({e}).")
        except Exception as e:
            print(f"MPRIS error: {e}")

    def _on_track_loaded(self, info: dict):
        if self.running and hasattr(self, 'mpris_object'):
            self.mpris_object.update_metadata(
                info.get("title", "Unknown"),
                info.get("artist", ""),
                info.get("thumbnail_url", "")
            )

    def _on_state_changed(self, is_playing: bool):
        if self.running and hasattr(self, 'mpris_object'):
            self.mpris_object.update_status(is_playing)
