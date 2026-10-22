import json
import os
import shutil
import tempfile
from core.app_paths import config_dir
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal


PLAYLISTS_DIR = str(config_dir() / "playlists")
COVERS_DIR = str(config_dir() / "covers")


class PlaylistManager(QObject):
    """Manages playlists with JSON file persistence."""

    playlist_created = pyqtSignal(str)    # playlist name
    playlist_updated = pyqtSignal(str)    # playlist name
    playlist_deleted = pyqtSignal(str)    # playlist name

    def __init__(self, sync_manager=None, parent=None):
        super().__init__(parent)
        os.makedirs(PLAYLISTS_DIR, exist_ok=True)
        os.makedirs(COVERS_DIR, exist_ok=True)

        self._sync_manager = sync_manager

        # Debounced sync — wait 3s after last change before syncing
        from PyQt6.QtCore import QTimer
        self._sync_debounce = QTimer(self)
        self._sync_debounce.setSingleShot(True)
        self._sync_debounce.setInterval(3000)
        self._sync_debounce.timeout.connect(self._trigger_sync)

    def set_sync_manager(self, sync_manager):
        """Set or update the sync manager reference."""
        self._sync_manager = sync_manager

    def _request_sync(self):
        """Request a debounced sync after a playlist change."""
        self._sync_debounce.start()  # restarts the 3s timer

    def _trigger_sync(self):
        """Actually trigger the sync."""
        if self._sync_manager and self._sync_manager.is_logged_in():
            self._sync_manager.sync_now()

    def _path(self, name: str) -> str:
        safe = name.replace("/", "_").replace("\\", "_")
        return os.path.join(PLAYLISTS_DIR, f"{safe}.json")

    def _cover_path(self, name: str) -> str:
        """Return the expected cover image path for a playlist."""
        safe = name.replace("/", "_").replace("\\", "_")
        return os.path.join(COVERS_DIR, f"{safe}.png")

    def list_playlists(self) -> list[str]:
        """Return sorted list of playlist names."""
        names = []
        if os.path.exists(PLAYLISTS_DIR):
            for f in os.listdir(PLAYLISTS_DIR):
                if f.endswith(".json"):
                    names.append(f[:-5])
        names.sort()
        return names

    def create_playlist(self, name: str) -> bool:
        """Create a new empty playlist. Returns False if it already exists."""
        if not name.strip():
            return False
        path = self._path(name)
        if os.path.exists(path):
            return False

        data = {
            "name": name,
            "created_at": datetime.now().isoformat(),
            "cover_image": "",
            "tracks": [],
        }
        self._save(name, data)

        self.playlist_created.emit(name)
        return True

    def delete_playlist(self, name: str):
        path = self._path(name)
        if os.path.exists(path):
            os.remove(path)
        # Also remove cover image
        cover = self._cover_path(name)
        if os.path.exists(cover):
            os.remove(cover)
        self._request_sync()
        self.playlist_deleted.emit(name)

    def rename_playlist(self, old_name: str, new_name: str) -> bool:
        if not new_name.strip():
            return False
        old_path = self._path(old_name)
        new_path = self._path(new_name)
        if not os.path.exists(old_path) or os.path.exists(new_path):
            return False

        data = self._load(old_name)
        data["name"] = new_name
        if os.path.exists(self._cover_path(old_name)):
            data["cover_image"] = self._cover_path(new_name)
        self._save(new_name, data)
        os.remove(old_path)

        # Move cover image if exists
        old_cover = self._cover_path(old_name)
        if os.path.exists(old_cover):
            new_cover = self._cover_path(new_name)
            shutil.move(old_cover, new_cover)

        self.playlist_deleted.emit(old_name)
        self.playlist_created.emit(new_name)
        return True

    def get_tracks(self, name: str) -> list[dict]:
        data = self._load(name)
        return data.get("tracks", [])

    def add_track(self, playlist_name: str, track: dict):
        """Add a track dict to the playlist."""
        data = self._load(playlist_name)
        # Avoid exact duplicates by URL
        urls = {t.get("url") for t in data["tracks"]}
        if track.get("url") not in urls:
            data["tracks"].append(track)
            self._save(playlist_name, data)
            self.playlist_updated.emit(playlist_name)

    def remove_track(self, playlist_name: str, index: int):
        data = self._load(playlist_name)
        if 0 <= index < len(data["tracks"]):
            data["tracks"].pop(index)
            self._save(playlist_name, data)
            self.playlist_updated.emit(playlist_name)

    def set_cover_image(self, playlist_name: str, source_path: str) -> str:
        """Copy the given image file as the playlist's cover. Returns the stored path."""
        dest = self._cover_path(playlist_name)
        if os.path.abspath(source_path) != os.path.abspath(dest):
            shutil.copy2(source_path, dest)
        # Also store reference in the JSON
        data = self._load(playlist_name)
        data["cover_image"] = dest
        self._save(playlist_name, data)
        self.playlist_updated.emit(playlist_name)
        return dest

    def get_cover_image(self, playlist_name: str) -> str:
        """Return the cover image path if it exists, otherwise empty string."""
        cover = self._cover_path(playlist_name)
        if os.path.exists(cover):
            return cover
        return ""

    def _load(self, name: str) -> dict:
        path = self._path(name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"name": name, "tracks": []}

    def _save(self, name: str, data: dict):
        path = self._path(name)
        fd, temporary = tempfile.mkstemp(dir=PLAYLISTS_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        self._request_sync()
