import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication
from core.recommendations import (ListeningHistory, RecommendationManager,
                                  build_profile, rank_tracks, track_key)

app = QApplication.instance() or QApplication([])


def track(title, artist='Artist', url=None):
    return {'title': title, 'uploader': artist, 'url': url or 'https://example.com/' + title,
            'platform': 'YouTube Music', 'duration': 180}


class FakePlayer(QObject):
    track_started = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.mpv = MagicMock(pause=False, idle_active=False, time_pos=1, duration=180)
        self._current_track = {}


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 0
        self.player = FakePlayer()
        self.path = Path(self.temp.name) / 'history.json'
        self.history = ListeningHistory(self.player, path=self.path, clock=lambda: self.now)
        self.history.timer.stop()

    def advance(self, seconds):
        for _ in range(seconds):
            self.now += 1
            self.history._tick()

    def test_qualified_listening_persists_once_per_session(self):
        song = track('Song')
        self.player.track_started.emit(song)
        self.advance(29)
        self.assertFalse(self.history.entries)
        self.advance(31)
        self.assertEqual(self.history.entries[track_key(song)]['plays'], 1)
        loaded = ListeningHistory(self.player, path=self.path)
        loaded.timer.stop()
        self.assertEqual(loaded.entries[track_key(song)]['plays'], 1)
        self.player.track_started.emit(song)
        self.advance(30)
        self.assertEqual(self.history.entries[track_key(song)]['plays'], 2)

    def test_pause_loading_and_quick_skip_do_not_count(self):
        self.player.track_started.emit(track('Skipped'))
        self.advance(5)
        self.player.track_started.emit(track('Paused'))
        self.player.mpv.pause = True
        self.advance(40)
        self.player.mpv.pause = False
        self.player.mpv.idle_active = True
        self.advance(40)
        self.assertFalse(self.history.entries)

    def test_seeking_does_not_inflate_listening(self):
        self.player.track_started.emit(track('Seek'))
        self.player.mpv.time_pos = 170
        self.advance(1)
        self.assertFalse(self.history.entries)

    def test_corrupted_history_is_tolerated(self):
        self.path.write_text('{bad json')
        loaded = ListeningHistory(self.player, path=self.path)
        loaded.timer.stop()
        self.assertFalse(loaded.entries)


class RankingTests(unittest.TestCase):
    def test_youtube_links_are_deduplicated(self):
        a = {'url': 'https://music.youtube.com/watch?v=abc&list=xyz'}
        b = {'url': 'https://youtu.be/abc?t=12'}
        self.assertEqual(track_key(a), track_key(b))

    def test_history_frequency_and_recency_affect_weight(self):
        now = time.time()
        recent, old = track('Recent'), track('Old')
        entries = {track_key(recent): {'track': recent, 'plays': 8, 'last_played': now},
                   track_key(old): {'track': old, 'plays': 8, 'last_played': now - 86400 * 180}}
        profile = build_profile([], entries, now)
        self.assertGreater(profile[1][track_key(recent)], profile[1][track_key(old)])

    def test_playlist_duplicates_do_not_dominate_profile(self):
        song = track('Saved')
        profile = build_profile([song, song, song], {})
        self.assertEqual(profile[1][track_key(song)], 2)

    def test_discovery_excludes_known_current_duplicates_and_unrelated(self):
        saved = track('Saved')
        new = track('New')
        playing = track('Playing')
        profile = build_profile([saved], {})
        result = rank_tracks([saved, new, dict(new), playing, track('Unrelated', 'Other')],
                             profile, playing['url'], discovery=True)
        self.assertEqual([item['title'] for item in result], ['New'])
        self.assertIn('Artist', result[0]['recommendation_reason'])

    def test_artist_diversity(self):
        songs = [track('Song' + str(i)) for i in range(5)] + [track('Other', 'Second')]
        profile = build_profile(songs, {})
        result = rank_tracks(songs, profile)
        self.assertEqual(len(result), 3)
        self.assertIn('Second', [item['uploader'] for item in result])


class ManagerTests(unittest.TestCase):
    def test_empty_profile_makes_no_network_calls(self):
        player = FakePlayer()
        history = MagicMock(entries={})
        manager = RecommendationManager(player, None, history)
        with patch('core.recommendations.SearchWorker') as search:
            manager.refresh()
            search.assert_not_called()
        manager.shutdown()

    def test_library_recommendations_work_when_discovery_fails(self):
        player = FakePlayer()
        history = MagicMock(entries={})
        playlists = MagicMock()
        playlists.list_playlists.return_value = ['Saved']
        playlists.get_tracks.return_value = [track('Saved')]
        manager = RecommendationManager(player, playlists, history)
        emitted = []
        manager.updated.connect(emitted.append)
        with patch('core.recommendations.SearchWorker') as search:
            manager.refresh()
            self.assertEqual(emitted[0][0]['title'], 'Saved')
            manager._error('offline')
            manager._finished()
            self.assertEqual(emitted[-1][0]['title'], 'Saved')
            search.assert_called_once()
        manager.shutdown()
