import random
import mpv
import time
from PyQt6.QtCore import QObject, pyqtSignal, Qt, QTimer
from core.recommendations import track_key
from core.audio_prefetch import AudioPrefetcher


class MusicPlayer(QObject):
    # Signals to communicate with the GUI thread
    time_pos_changed = pyqtSignal(float)
    duration_changed = pyqtSignal(float)
    state_changed = pyqtSignal(bool)  # True if playing, False if paused/stopped
    track_started = pyqtSignal(dict)  # A new playback session, distinct from metadata updates
    track_loaded = pyqtSignal(dict)   # {title, artist, thumbnail_url, platform, ...}
    track_ended = pyqtSignal()        # Emitted when track ends naturally
    queue_started = pyqtSignal()      # New explicitly selected track/playlist
    queue_updated = pyqtSignal()      # Emitted when priority or base queue changes
    shuffle_changed = pyqtSignal(bool)
    prefetch_changed = pyqtSignal(str)

    def __init__(self, theme_manager=None):
        super().__init__()
        self.theme_manager = theme_manager
        self._pending_metadata = None
        
        # Queue state
        self._base_queue: list[dict] = []
        self._current_base_index = -1
        
        self._priority_queue: list[dict] = []
        self._recommended_queue: list[dict] = []
        self._recommendation_seen = set()
        self._recommendation_context = []
        self._queue_session = 0
        self._awaiting_recommendations = False
        self._prefetch_active = False
        self._history: list[dict] = []
        self._current_track: dict = {}
        self._current_track_source: str = "base"
        
        self._shuffle = False
        self._shuffled_indices: list[int] = []
        
        self._repeat_mode = 0  # 0: Off, 1: Loop All, 2: Loop One

        self._master_volume = 100
        self._cf_fading_in_idx = 0
        self._cf_fading_out_idx = 1
        
        # Dual MPV instances for Crossfade
        # config=False prevents MPV from loading user's mpv.conf which could trigger playback
        # idle=True keeps MPV in idle state without playing anything on startup
        self.players = [
            mpv.MPV(ytdl=True, video=False, config=False, idle=True),
            mpv.MPV(ytdl=True, video=False, config=False, idle=True)
        ]
        self.active_idx = 0
        
        # State for crossfading
        self._is_crossfading = False
        self._crossfade_timer = QTimer(self)
        self._crossfade_timer.setInterval(50)  # 20 ticks per second
        self._crossfade_timer.timeout.connect(self._crossfade_tick)

        self._last_duration = None
        self._last_paused = None
        self._last_media_title = None
        self._last_idle_state = True

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(150)
        self._poll_timer.timeout.connect(self._poll_mpv_state)
        self._poll_timer.start()

        self.track_ended.connect(self._on_track_ended, Qt.ConnectionType.QueuedConnection)
        self.prefetcher = AudioPrefetcher(self)
        self.prefetcher.status_changed.connect(self._on_prefetch_status)
        self._prefetch_timer = QTimer(self)
        self._prefetch_timer.setSingleShot(True)
        self._prefetch_timer.setInterval(100)
        self._prefetch_timer.timeout.connect(self._prepare_next)
        self.queue_updated.connect(self._schedule_prefetch)
        self.track_started.connect(self._schedule_prefetch)

        
        if self.theme_manager:
            self.theme_manager.theme_changed.connect(self.apply_equalizer)
            self.theme_manager.theme_changed.connect(self._schedule_prefetch)
            self.apply_equalizer()

    def _schedule_prefetch(self, *_):
        self._prefetch_timer.start()

    def _prepare_next(self):
        enabled = not self.theme_manager or self.theme_manager.current_theme.get("PREFETCH_ENABLED", True)
        track, _ = self._get_next_track_info() if self._current_track and enabled and self._prefetch_active else (None, "")
        url = track.get("url", "") if track else ""
        if track and (track.get("is_live") or (track.get("duration") or 0) > 1200):
            url = ""
        current = self._current_track.get("url", "")
        self.prefetcher.request(url, protected_urls=(current, url))

    def _playback_source(self, url):
        return self.prefetcher.cached_path(url) or url

    def _on_prefetch_status(self, url, state):
        messages = {"downloading": "Pobieram następny utwór…", "ready": "Następny utwór gotowy",
                    "unavailable": "Następny utwór odtworzy się online", "idle": ""}
        self.prefetch_changed.emit(messages[state])

    @property
    def mpv(self):
        """Returns the primary active mpv instance. Backwards compatible for simple calls."""
        return self.players[self.active_idx]

    def apply_equalizer(self):
        if not self.theme_manager:
            return
        bass = self.theme_manager.current_theme.get("BASS_GAIN", 0)
        treble = self.theme_manager.current_theme.get("TREBLE_GAIN", 0)
        
        filter_str = f"lavfi=[bass=g={bass}:f=110:w=0.6,treble=g={treble}:f=10000:w=0.5]"
        for p in self.players:
            p.af = filter_str

    def _poll_mpv_state(self):
        # 1. Check duration
        duration = None
        try:
            duration = self.mpv.duration
            if duration is not None and duration != self._last_duration:
                self._last_duration = duration
                self.duration_changed.emit(duration)
        except Exception:
            pass

        # 2. Check time-pos
        try:
            value = self.mpv.time_pos
            if value is not None:
                self.time_pos_changed.emit(value)
                
                # Check if we should start crossfade
                if self.theme_manager and self.theme_manager.current_theme.get("CROSSFADE_ENABLED", True):
                    if duration and not self._is_crossfading:
                        cf_duration = self.theme_manager.current_theme.get("CROSSFADE_DURATION", 5)
                        time_left = duration - value
                        # If we are within crossfade duration and track has played for a bit
                        if time_left <= cf_duration and value > cf_duration:
                            self._start_crossfade(cf_duration)
        except Exception:
            pass

        # 3. Check pause state
        try:
            paused = self.mpv.pause
            if paused is not None and paused != self._last_paused:
                self._last_paused = paused
                self.state_changed.emit(not paused and not self.mpv.idle_active)
        except Exception:
            pass

        # 4. Check media-title
        try:
            title = self.mpv.media_title
            if title is not None and title != self._last_media_title:
                self._last_media_title = title
                meta = {
                    "title": (self._pending_metadata or {}).get("title") or title,
                    "artist": "",
                }
                if self._pending_metadata:
                    meta["artist"] = self._pending_metadata.get("uploader", "")
                    meta["thumbnail_url"] = self._pending_metadata.get("thumbnail_url", "")
                    meta["platform"] = self._pending_metadata.get("platform", "")
                self.track_loaded.emit(meta)
        except Exception:
            pass

        # 5. Check idle-active state
        try:
            is_idle = self.mpv.idle_active
            if is_idle != self._last_idle_state:
                self._last_idle_state = is_idle
                if is_idle and self._current_track and not self._is_crossfading:
                    self.state_changed.emit(False)
                    self.track_ended.emit()
        except Exception:
            pass

    def set_track_metadata(self, metadata: dict):
        self._pending_metadata = metadata
        self.track_started.emit(dict(metadata))
        info = {
            "title": metadata.get("title", "Unknown"),
            "artist": metadata.get("uploader", "Unknown Artist"),
            "thumbnail_url": metadata.get("thumbnail_url", ""),
            "platform": metadata.get("platform", ""),
        }
        self.track_loaded.emit(info)

    def play_url(self, url, start_paused=False):
        self._prefetch_active = True
        self._awaiting_recommendations = False
        # Stop crossfading if we explicitly play a new URL
        if self._is_crossfading:
            self._crossfade_timer.stop()
            self._is_crossfading = False
            self.players[1 - self.active_idx].command("stop")
            self.mpv.volume = self._master_volume

        self._last_duration = None
        self._last_media_title = None
        self._last_idle_state = True
        self.time_pos_changed.emit(0)
        self.duration_changed.emit(0)
        self.mpv.volume = self._master_volume
        self.mpv.play(self._playback_source(url))
        self.mpv.pause = start_paused
        if not start_paused:
            self.state_changed.emit(True)
        
    def play_queue(self, tracks: list[dict], start_index: int = 0):
        if not tracks:
            return
        self._base_queue = [dict(track) for track in tracks]
        self._current_base_index = max(0, min(start_index, len(tracks) - 1))
        self._priority_queue.clear()
        self._recommended_queue.clear()
        self._recommendation_seen.clear()
        self._recommendation_context = [dict(track) for track in tracks]
        self._queue_session += 1
        self._history.clear()
        self._current_track = {}
        
        if self._shuffle:
            self._generate_shuffled_indices()
            
        self._play_base_index(self._current_base_index)
        self.queue_started.emit()
        self.queue_updated.emit()

    def add_to_queue(self, track: dict, play_next: bool = False):
        key = track_key(track)
        self._recommended_queue = [t for t in self._recommended_queue if track_key(t) != key]
        self._recommendation_seen.add(key)
        if play_next:
            self._priority_queue.insert(0, track)
        else:
            if self._priority_queue and self._priority_queue[-1].get("url") == track.get("url"):
                return
            self._priority_queue.append(track)
        self.queue_updated.emit()

    def move_priority_track(self, from_index: int, to_index: int):
        if 0 <= from_index < len(self._priority_queue) and 0 <= to_index <= len(self._priority_queue):
            track = self._priority_queue.pop(from_index)
            self._priority_queue.insert(to_index, track)
            self.queue_updated.emit()

    def upcoming_base_tracks(self):
        if self._shuffle:
            return [self._base_queue[i] for i in self._shuffled_indices
                    if 0 <= i < len(self._base_queue)]
        return self._base_queue[self._current_base_index + 1:]

    def queue_edit_snapshot(self):
        """Identity and order of the editable main queue, including duplicate URLs."""
        return (self._queue_session, self._shuffle, self._current_base_index,
                tuple(id(track) for track in self._priority_queue),
                tuple(id(track) for track in self.upcoming_base_tracks()))

    def move_queue_item(self, source, index, target, position, expected_key=None, snapshot=None):
        """Insert at a boundary in the displayed queue; reject a stale main-queue view."""
        if snapshot is not None and snapshot != self.queue_edit_snapshot():
            return False
        if target not in ('priority', 'base') or source not in ('priority', 'base', 'recommended'):
            return False
        destination = self._priority_queue if target == 'priority' else self.upcoming_base_tracks()
        if not 0 <= position <= len(destination):
            return False
        if source == 'recommended':
            return self.promote_recommended(index, target, position, expected_key)
        origin = self._priority_queue if source == 'priority' else self.upcoming_base_tracks()
        if not 0 <= index < len(origin):
            return False
        if expected_key is not None and track_key(origin[index]) != expected_key:
            return False
        if source == target:
            adjusted = position - (index < position)
            if adjusted == index:
                return True
            if source == 'priority':
                self.move_priority_track(index, adjusted)
            else:
                self.move_upcoming_base_track(index, adjusted)
            return True

        if source == 'priority':
            track = self._priority_queue.pop(index)
        else:
            absolute = self._shuffled_indices[index] if self._shuffle else self._current_base_index + 1 + index
            track = self._base_queue.pop(absolute)
            self._shuffled_indices = [i - (i > absolute) for i in self._shuffled_indices if i != absolute]
            if absolute <= self._current_base_index:
                self._current_base_index -= 1
        if target == 'priority':
            self._priority_queue.insert(position, track)
        elif self._shuffle:
            self._base_queue.append(track)
            self._shuffled_indices.insert(position, len(self._base_queue) - 1)
        else:
            self._base_queue.insert(self._current_base_index + 1 + position, track)
        self._recommendation_seen.add(track_key(track))
        self.queue_updated.emit()
        return True

    def remove_queue_item(self, source, index, expected_key=None, snapshot=None):
        """Remove an upcoming entry from this session without editing its saved playlist."""
        if snapshot is not None and snapshot != self.queue_edit_snapshot():
            return False
        if source not in ('priority', 'base', 'recommended'):
            return False
        origin = {'priority': self._priority_queue, 'base': self.upcoming_base_tracks(),
                  'recommended': self._recommended_queue}[source]
        if source == 'recommended' and expected_key is not None:
            index = next((i for i, track in enumerate(origin) if track_key(track) == expected_key), -1)
        if not 0 <= index < len(origin):
            return False
        if expected_key is not None and track_key(origin[index]) != expected_key:
            return False
        track = origin[index]
        if source == 'base':
            absolute = self._shuffled_indices[index] if self._shuffle else self._current_base_index + 1 + index
            self._base_queue.pop(absolute)
            self._shuffled_indices = [i - (i > absolute) for i in self._shuffled_indices if i != absolute]
            if absolute <= self._current_base_index:
                self._current_base_index -= 1
        else:
            origin.pop(index)
        self._recommendation_seen.add(track_key(track))
        self.queue_updated.emit()
        return True

    def move_upcoming_base_track(self, from_relative_idx: int, to_relative_idx: int):
        if self._shuffle:
            if 0 <= from_relative_idx < len(self._shuffled_indices) and 0 <= to_relative_idx < len(self._shuffled_indices):
                idx = self._shuffled_indices.pop(from_relative_idx)
                self._shuffled_indices.insert(to_relative_idx, idx)
                self.queue_updated.emit()
        else:
            offset = self._current_base_index + 1
            abs_from = offset + from_relative_idx
            abs_to = offset + to_relative_idx
            if 0 <= abs_from < len(self._base_queue) and 0 <= abs_to < len(self._base_queue):
                track = self._base_queue.pop(abs_from)
                self._base_queue.insert(abs_to, track)
                self.queue_updated.emit()
        
    def _play_track_dict(self, track: dict, source: str = "base"):
        if self._current_track:
            self._current_track["_source"] = getattr(self, "_current_track_source", "base")
            self._history.append(dict(self._current_track))
        self._current_track = dict(track)
        self._current_track_source = source
        self.set_track_metadata(track)
        self.play_url(track.get("url", ""))

    def _get_next_track_info(self):
        """Ordinary queue always precedes the suggested continuation."""
        if self._repeat_mode == 2 and self._current_track:
            return self._current_track, self._current_track_source
        if self._priority_queue:
            return self._priority_queue[0], "priority"
        if self._base_queue:
            if self._shuffle:
                if self._shuffled_indices:
                    return self._base_queue[self._shuffled_indices[0]], "shuffle"
                if self._repeat_mode == 1:
                    self._generate_shuffled_indices()
                    index = self._shuffled_indices[0] if self._shuffled_indices else self._current_base_index
                    return self._base_queue[index], "shuffle"
            else:
                if self._current_base_index + 1 < len(self._base_queue):
                    return self._base_queue[self._current_base_index + 1], "base"
                if self._repeat_mode == 1:
                    return self._base_queue[0], "base"
        if self._recommended_queue:
            return self._recommended_queue[0], "recommended"
        return None, ""

    def _pop_next_track(self):
        track, source = self._get_next_track_info()
        if not track or self._repeat_mode == 2:
            return track, source
        if source == "priority":
            return self._priority_queue.pop(0), source
        if source == "recommended":
            track = self._recommended_queue.pop(0)
            self._recommendation_seen.add(track_key(track))
            return track, source
        if source == "shuffle":
            if not self._shuffled_indices:
                self._generate_shuffled_indices()
            if self._shuffled_indices:
                self._current_base_index = self._shuffled_indices.pop(0)
        else:
            self._current_base_index = (self._current_base_index + 1) % len(self._base_queue)
        return self._base_queue[self._current_base_index], source

    def set_recommended_queue(self, tracks):
        excluded = {track_key(t) for t in self._base_queue + self._priority_queue}
        excluded.update(self._recommendation_seen)
        excluded.add(track_key(self._current_track))
        result = []
        for track in tracks:
            key = track_key(track)
            if key and key not in excluded:
                result.append(dict(track))
                excluded.add(key)
        if result != self._recommended_queue:
            self._recommended_queue = result
            self.queue_updated.emit()
        if result and self._awaiting_recommendations:
            self._awaiting_recommendations = False
            self.next_track()

    def promote_recommended(self, index, target="priority", position=None, expected_key=None):
        """Move a suggestion into the session queue without editing a saved playlist."""
        if target not in ("priority", "base"):
            return False
        if expected_key is not None:
            index = next((i for i, track in enumerate(self._recommended_queue)
                          if track_key(track) == expected_key), -1)
        if not 0 <= index < len(self._recommended_queue):
            return False
        track = self._recommended_queue[index]
        self._recommended_queue.pop(index)
        self._recommendation_seen.add(track_key(track))
        if target == "priority":
            position = len(self._priority_queue) if position is None else position
            self._priority_queue.insert(max(0, min(position, len(self._priority_queue))), track)
        elif self._shuffle:
            new_index = len(self._base_queue)
            self._base_queue.append(track)
            position = len(self._shuffled_indices) if position is None else position
            self._shuffled_indices.insert(max(0, min(position, len(self._shuffled_indices))), new_index)
        else:
            offset = self._current_base_index + 1
            remaining = len(self._base_queue) - offset
            position = remaining if position is None else max(0, min(position, remaining))
            self._base_queue.insert(offset + position, track)
        self.queue_updated.emit()
        return True

    def play_queued_track(self, queue_type, index):
        if queue_type == "priority" and 0 <= index < len(self._priority_queue):
            track = self._priority_queue.pop(index)
            self._play_track_dict(track, "priority")
        elif queue_type == "recommended" and 0 <= index < len(self._recommended_queue):
            track = self._recommended_queue.pop(index)
            self._recommendation_seen.add(track_key(track))
            self._play_track_dict(track, "recommended")
        elif queue_type == "base":
            if self._shuffle:
                if not 0 <= index < len(self._shuffled_indices):
                    return
                absolute = self._shuffled_indices.pop(index)
            else:
                absolute = self._current_base_index + 1 + index
            if not 0 <= absolute < len(self._base_queue):
                return
            self._play_base_index(absolute)
        else:
            return
        self.queue_updated.emit()

    def remove_recommended(self, index):
        if 0 <= index < len(self._recommended_queue):
            track = self._recommended_queue.pop(index)
            self._recommendation_seen.add(track_key(track))
            self.queue_updated.emit()

    def _on_track_ended(self):
        if not self.next_track():
            self._awaiting_recommendations = True

    def next_track(self):
        track, source = self._pop_next_track()
        if track:
            self._awaiting_recommendations = False
            self._play_track_dict(track, source=source)
            self.queue_updated.emit()
            return True
        return False

    def prev_track(self):
        if self._is_crossfading:
            self._crossfade_timer.stop()
            self._is_crossfading = False
            self.players[1 - self.active_idx].command("stop")

        if self._repeat_mode == 2 and self._current_track:
            self.set_track_metadata(self._current_track)
            self.play_url(self._current_track.get("url", ""))
            return
            
        if self._history:
            track_to_restore = self._current_track
            source = getattr(self, "_current_track_source", "base")
            
            if track_to_restore:
                if source == "priority":
                    self._priority_queue.insert(0, track_to_restore)
                elif source == "recommended":
                    self._recommendation_seen.discard(track_key(track_to_restore))
                    self._recommended_queue.insert(0, track_to_restore)
                elif source == "shuffle":
                    for i, t in enumerate(self._base_queue):
                        if t.get("url") == track_to_restore.get("url"):
                            self._shuffled_indices.insert(0, i)
                            break

            track = self._history.pop()
            
            for i, t in enumerate(self._base_queue):
                if t.get("url") == track.get("url"):
                    self._current_base_index = i
                    break
                    
            self._current_track_source = track.get("_source", "base")
            self._current_track = dict(track)
            self.set_track_metadata(track)
            self.play_url(track.get("url", ""))
            self.queue_updated.emit()
        else:
            if self._current_track:
                self.set_track_metadata(self._current_track)
                self.play_url(self._current_track.get("url", ""))

    def _start_crossfade(self, cf_duration):
        next_track, source = self._get_next_track_info()
        if not next_track:
            return  # End of queue, let it finish naturally

        # We pop it so the queue logic advances
        track, source = self._pop_next_track()
        if not track:
            return

        if self._current_track:
            self._current_track["_source"] = getattr(self, "_current_track_source", "base")
            self._history.append(dict(self._current_track))

        self._current_track = dict(track)
        self._current_track_source = source
        self.queue_updated.emit()

        # Remember which player is fading out (old) and fading in (new)
        self._cf_fading_out_idx = self.active_idx
        self._cf_fading_in_idx = 1 - self.active_idx

        # Load next track into the NEW player
        new_mpv = self.players[self._cf_fading_in_idx]
        new_mpv.volume = 0
        try:
            new_mpv.play(self._playback_source(track.get("url", "")))
        except Exception:
            pass
        try:
            new_mpv.volume = 0
        except Exception:
            pass
        new_mpv.pause = False

        self._is_crossfading = True
        self._cf_start_real_time = time.monotonic()
        self._cf_duration = cf_duration
        self._crossfade_timer.start()

        # Switch active player to new one for UI updates
        self.active_idx = self._cf_fading_in_idx
        self.set_track_metadata(track)

    def _crossfade_tick(self):
        fading_out_mpv = self.players[self._cf_fading_out_idx]
        fading_in_mpv = self.players[self._cf_fading_in_idx]

        elapsed = time.monotonic() - self._cf_start_real_time

        is_out_idle = False
        try:
            is_out_idle = fading_out_mpv.idle_active
        except Exception:
            pass

        if elapsed >= self._cf_duration or is_out_idle:
            # Crossfade complete
            self._crossfade_timer.stop()
            self._is_crossfading = False
            try:
                fading_out_mpv.command("stop")
            except Exception:
                pass
            try:
                fading_in_mpv.volume = self._master_volume
            except Exception:
                pass
        else:
            # Calculate volumes
            ratio = max(0.0, min(1.0, elapsed / self._cf_duration)) if self._cf_duration > 0 else 1.0
            try:
                fading_out_mpv.volume = self._master_volume * (1.0 - ratio)
            except Exception:
                pass
            try:
                fading_in_mpv.volume = self._master_volume * ratio
            except Exception:
                pass

    def _play_base_index(self, index: int):
        if 0 <= index < len(self._base_queue):
            self._current_base_index = index
            source = "shuffle" if self._shuffle else "base"
            self._play_track_dict(self._base_queue[index], source=source)

    def _generate_shuffled_indices(self):
        if not self._base_queue:
            self._shuffled_indices = []
            return
            
        indices = list(range(len(self._base_queue)))
        if self._current_base_index in indices:
            indices.remove(self._current_base_index)
        random.shuffle(indices)
        self._shuffled_indices = indices

    def toggle_shuffle(self) -> bool:
        self._shuffle = not self._shuffle
        if self._shuffle:
            self._generate_shuffled_indices()
        else:
            self._shuffled_indices.clear()
        self.shuffle_changed.emit(self._shuffle)
        self.queue_updated.emit()
        return self._shuffle

    def shuffle_queue(self):
        if self._priority_queue:
            random.shuffle(self._priority_queue)
            
        if not self._shuffle:
            self._shuffle = True
            self.shuffle_changed.emit(True)
            
        self._generate_shuffled_indices()
        self.queue_updated.emit()

    def toggle_repeat(self) -> int:
        self._repeat_mode = (self._repeat_mode + 1) % 3
        self.queue_updated.emit()
        return self._repeat_mode

    def toggle_pause(self):
        if self.mpv.idle_active:
            if self._current_track:
                self.play_url(self._current_track.get("url", ""))
            return
        paused = not self.mpv.pause
        if self._is_crossfading:
            if paused:
                self._cf_paused_at = time.monotonic()
                self._crossfade_timer.stop()
            else:
                self._cf_start_real_time += time.monotonic() - self._cf_paused_at
                self._crossfade_timer.start()
            for player in self.players:
                player.pause = paused
        else:
            self.mpv.pause = paused

    def set_volume(self, value):
        self._master_volume = value
        if not self._is_crossfading:
            self.mpv.volume = value

    def seek(self, percentage):
        if self.mpv.duration:
            target_time = (percentage / 100.0) * self.mpv.duration
            self.mpv.seek(target_time, reference='absolute')

    def stop(self):
        self._prefetch_active = False
        self._prefetch_timer.stop()
        self.prefetcher.request("")
        self._awaiting_recommendations = False
        self._crossfade_timer.stop()
        self._is_crossfading = False
        self._last_idle_state = True
        for player in self.players:
            player.command("stop")
        self.time_pos_changed.emit(0)
        self.state_changed.emit(False)

    def shutdown(self):
        self._poll_timer.stop()
        self._prefetch_timer.stop()
        self.prefetcher.shutdown()
        self.stop()
        for player in self.players:
            player.terminate()
