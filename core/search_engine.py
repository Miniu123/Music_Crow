import json
import os
import signal
import subprocess
import sys
import time
from PyQt6.QtCore import QThread, pyqtSignal


def run_extractor(worker, command, timeout):
    """Keep subprocess cancellation responsive without blocking the GUI."""
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, start_new_session=(os.name == "posix")) as process:
        def kill_process_tree():
            try:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + timeout
        while True:
            if worker.isInterruptionRequested():
                kill_process_tree()
                process.communicate()
                raise InterruptedError()
            try:
                stdout, stderr = process.communicate(timeout=0.1)
                return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
            except subprocess.TimeoutExpired:
                if time.monotonic() >= deadline:
                    kill_process_tree()
                    process.communicate()
                    raise subprocess.TimeoutExpired(command, timeout)


PLATFORM_PREFIXES = {
    "YouTube Music": "ytsearch5:",
    "SoundCloud": "scsearch5:",
}

PLATFORM_COLORS = {
    "YouTube Music": "#FF0000",
    "SoundCloud": "#FF5500",
    "Spotify": "#1DB954",
}


def channel_metadata(data):
    """Retain source identity when tracks are searched, imported or saved."""
    return {key: data[key] for key in ('channel_url', 'channel_id', 'uploader_url', 'uploader_id')
            if isinstance(data.get(key), str) and data[key]}


class SearchWorker(QThread):
    """Runs yt-dlp search across multiple platforms in a background thread."""

    results_ready = pyqtSignal(list)
    search_error = pyqtSignal(str)

    def __init__(self, query: str, platforms: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.query = query
        self.platforms = list(PLATFORM_PREFIXES) if platforms is None else platforms

    def run(self):
        all_results = []
        errors = []

        for platform in self.platforms:
            if self.isInterruptionRequested():
                return
            prefix = PLATFORM_PREFIXES.get(platform, "ytsearch5:")
            search_url = f"{prefix}{self.query}"

            try:
                proc = run_extractor(
                    self,
                    [
                        sys.executable, "-m", "yt_dlp",
                        "--flat-playlist",
                        "--dump-json",
                        "--no-warnings",
                        "--ignore-errors",
                        search_url,
                    ],
                    timeout=30,
                )

                if self.isInterruptionRequested():
                    return
                if proc.returncode and not proc.stdout.strip():
                    errors.append(f"{platform}: {proc.stderr.strip()[-300:] or 'Search failed'}")

                for line in proc.stdout.strip().split("\n"):
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        result = {
                            **channel_metadata(data),
                            "title": data.get("title", "Unknown Title"),
                            "uploader": data.get("uploader", data.get("channel", "Unknown Artist")),
                            "duration": data.get("duration", 0),
                            "thumbnail_url": self._best_thumbnail(data),
                            "url": data.get("url", data.get("webpage_url", "")),
                            "platform": platform,
                        }
                        all_results.append(result)
                    except json.JSONDecodeError:
                        continue

            except InterruptedError:
                return
            except subprocess.TimeoutExpired:
                errors.append(f"{platform}: timed out")
            except FileNotFoundError:
                errors.append("yt-dlp not found")
                break
            except Exception as e:
                errors.append(f"{platform}: {e}")

        if all_results:
            self.results_ready.emit(all_results)
        elif errors:
            self.search_error.emit("; ".join(errors))
        else:
            self.results_ready.emit([])

    @staticmethod
    def _best_thumbnail(data: dict) -> str:
        """Extract the best available thumbnail URL."""
        thumbnails = data.get("thumbnails", [])
        if thumbnails:
            return thumbnails[-1].get("url", "")
        return data.get("thumbnail", "")


class PlaylistImportWorker(QThread):
    """Imports a playlist from a URL (YouTube Music, YouTube, SoundCloud) using yt-dlp."""

    progress = pyqtSignal(int, int)        # (current, total)
    track_imported = pyqtSignal(dict)       # single track dict
    import_finished = pyqtSignal(list)      # all tracks
    import_error = pyqtSignal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        all_tracks = []

        try:
            proc = run_extractor(
                self,
                [
                    sys.executable, "-m", "yt_dlp",
                    "--flat-playlist",
                    "--dump-json",
                    "--no-warnings",
                    "--ignore-errors",
                    self.url,
                ],
                timeout=120,
            )

            if proc.returncode and not proc.stdout.strip():
                self.import_error.emit(proc.stderr.strip()[-500:] or "Import failed")
                return

            lines = [l for l in proc.stdout.strip().split("\n") if l.strip()]
            total = len(lines)

            for i, line in enumerate(lines):
                try:
                    data = json.loads(line)

                    # Detect platform from URL
                    platform = "YouTube Music"
                    url_str = data.get("url", data.get("webpage_url", self.url))
                    if "soundcloud.com" in self.url:
                        platform = "SoundCloud"
                    elif "spotify.com" in self.url:
                        platform = "Spotify"

                    track = {
                        **channel_metadata(data),
                        "title": data.get("title", "Unknown Title"),
                        "uploader": data.get("uploader", data.get("channel", "Unknown Artist")),
                        "duration": data.get("duration", 0),
                        "thumbnail_url": SearchWorker._best_thumbnail(data),
                        "url": url_str,
                        "platform": platform,
                    }
                    all_tracks.append(track)
                    self.track_imported.emit(track)
                    self.progress.emit(i + 1, total)

                except json.JSONDecodeError:
                    continue

            self.import_finished.emit(all_tracks)

        except InterruptedError:
            return
        except subprocess.TimeoutExpired:
            self.import_error.emit("Import timed out (playlist may be too large)")
        except FileNotFoundError:
            self.import_error.emit("yt-dlp not found — install it with: pip install yt-dlp")
        except Exception as e:
            self.import_error.emit(str(e))
