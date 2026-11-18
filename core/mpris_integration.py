import threading
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, Qt

# Must match the installed .desktop file so desktops can show the app icon.
DESKTOP_ENTRY = "io.github.Miniu123.MusicCrow"


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
                   "previous": self.player.prev_track,
                   "stop": self.player.stop}
        actions[command]()

    def _init_mpris(self):
        try:
            import dbus
            import dbus.exceptions
            import dbus.service
            from dbus.mainloop.glib import DBusGMainLoop
            from gi.repository import GLib

            DBusGMainLoop(set_as_default=True)
            self.bus = dbus.SessionBus()
            
            ROOT_IFACE = "org.mpris.MediaPlayer2"
            PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"

            class MprisPlayer(dbus.service.Object):
                def __init__(self, bus, player_ref, commands):
                    self.player_ref = player_ref
                    self.commands = commands
                    self.path = "/org/mpris/MediaPlayer2"
                    dbus.service.Object.__init__(self, bus, self.path)
                    
                    self.PlaybackStatus = "Stopped"
                    self.Metadata = dbus.Dictionary({}, signature='sv')

                def _position(self):
                    try:
                        seconds = self.player_ref.mpv.time_pos or 0
                    except Exception:
                        seconds = 0
                    return dbus.Int64(int(seconds * 1_000_000))

                def _properties(self, interface):
                    """All MPRIS properties of an interface, as D-Bus typed values."""
                    if interface == ROOT_IFACE:
                        return {
                            "CanQuit": dbus.Boolean(False),
                            "CanRaise": dbus.Boolean(False),
                            "HasTrackList": dbus.Boolean(False),
                            "Identity": dbus.String("Music Crow"),
                            "DesktopEntry": dbus.String(DESKTOP_ENTRY),
                            "SupportedUriSchemes": dbus.Array([], signature='s'),
                            "SupportedMimeTypes": dbus.Array([], signature='s'),
                        }
                    if interface == PLAYER_IFACE:
                        volume = getattr(self.player_ref, "_master_volume", 100) / 100.0
                        return {
                            "PlaybackStatus": dbus.String(self.PlaybackStatus),
                            "Metadata": dbus.Dictionary(self.Metadata, signature='sv'),
                            "Rate": dbus.Double(1.0),
                            "MinimumRate": dbus.Double(1.0),
                            "MaximumRate": dbus.Double(1.0),
                            "Volume": dbus.Double(volume),
                            "Position": self._position(),
                            "CanControl": dbus.Boolean(True),
                            "CanPause": dbus.Boolean(True),
                            "CanPlay": dbus.Boolean(True),
                            "CanGoNext": dbus.Boolean(True),
                            "CanGoPrevious": dbus.Boolean(True),
                            "CanSeek": dbus.Boolean(False),
                        }
                    return None

                @dbus.service.method("org.freedesktop.DBus.Properties", in_signature='ss', out_signature='v')
                def Get(self, interface, prop):
                    properties = self._properties(interface)
                    if properties is None or prop not in properties:
                        raise dbus.exceptions.DBusException(
                            f"No such property {interface}.{prop}",
                            name="org.freedesktop.DBus.Error.InvalidArgs")
                    return properties[prop]

                @dbus.service.method("org.freedesktop.DBus.Properties", in_signature='s', out_signature='a{sv}')
                def GetAll(self, interface):
                    return dbus.Dictionary(self._properties(interface) or {}, signature='sv')

                @dbus.service.method("org.freedesktop.DBus.Properties", in_signature='ssv')
                def Set(self, interface, prop, value):
                    raise dbus.exceptions.DBusException(
                        f"Property {interface}.{prop} is read-only",
                        name="org.freedesktop.DBus.Error.PropertyReadOnly")

                @dbus.service.method(ROOT_IFACE)
                def Raise(self):
                    pass

                @dbus.service.method(ROOT_IFACE)
                def Quit(self):
                    pass

                @dbus.service.method(PLAYER_IFACE)
                def Stop(self):
                    self.commands.emit("stop")

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
