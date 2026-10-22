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
                                  build_profile, rank_tracks, track_key, recording_key, discovery_seeds)

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
    def test_artist_aliases_and_packaging_are_deduplicated_but_versions_survive(self):
        original = track('Artist - Song (Official Video)', 'ArtistVEVO', 'https://example.com/1')
        audio = track('Song [Official Audio]', 'Artist - Topic', 'https://example.com/2')
        remix = track('Song (Night Remix)', 'Artist', 'https://example.com/3')
        self.assertEqual(recording_key(original), recording_key(audio))
        self.assertNotEqual(recording_key(original), recording_key(remix))
        profile = build_profile([original], {})
        result = rank_tracks([audio, remix], profile, discovery=True)
        self.assertEqual([t['url'] for t in result], [remix['url']])

    def test_same_title_by_different_artists_is_not_a_duplicate(self):
        songs = [track('Home', 'One', 'https://example.com/one'),
                 track('Home', 'Two', 'https://example.com/two')]
        self.assertEqual(len(rank_tracks(songs, build_profile(songs, {}))), 2)

    def test_artist_match_uses_word_boundaries(self):
        profile = build_profile([track('Saved', 'Air')], {})
        self.assertEqual(rank_tracks([track('Stairway', 'Other')], profile, discovery=True), [])

    def test_recent_listening_is_temporarily_demoted(self):
        now = 2_000_000
        recent, older = track('Recent'), track('Older')
        entries = {track_key(t): {'track': t, 'plays': 8, 'last_played': last}
                   for t, last in [(recent, now), (older, now - 86400 * 2)]}
        profile = build_profile([], entries, now)
        result = rank_tracks([recent, older], profile)
        self.assertEqual(result[0]['title'], 'Older')

    def test_active_artist_beats_large_unrelated_library(self):
        saved = [track(str(i), 'Large artist') for i in range(100)] + [track('Current', 'Session')]
        profile = build_profile(saved, {}, context=[saved[-1]])
        result = rank_tracks([track('New hit', 'Large artist'), track('New session', 'Session')],
                             profile, discovery=True)
        self.assertEqual(result[0]['uploader'], 'Session')
        self.assertEqual(result[0]['recommendation_reason'], 'Pasuje do teraz: Session')

    def test_related_artists_require_playlist_evidence(self):
        active, neighbour, unrelated = track('Current', 'Anchor'), track('Saved', 'Neighbour'), track('Other', 'Elsewhere')
        profile = build_profile([active], {}, context=[active],
                                playlist_groups=[[active, neighbour], [unrelated]])
        result = rank_tracks([track('New', 'Neighbour'), track('Random', 'Elsewhere')], profile, discovery=True)
        self.assertEqual([t['uploader'] for t in result], ['Neighbour'])
        self.assertIn('Powiązane przez playlisty:', result[0]['recommendation_reason'])

    def test_explicit_collaborator_can_be_discovered(self):
        saved = track('Night (feat. Guest)', 'Anchor')
        profile = build_profile([saved], {})
        self.assertIn('Guest', discovery_seeds(profile))
        result = rank_tracks([track('Solo', 'Guest'), track('Random', 'Stranger')], profile, discovery=True)
        self.assertEqual([t['uploader'] for t in result], ['Guest'])

    def test_seed_rotation_keeps_anchors_and_explores_less_common_artists(self):
        profile = build_profile([track(str(i), 'Artist ' + str(i)) for i in range(9)], {})
        first, second = discovery_seeds(profile, 0), discovery_seeds(profile, 1)
        self.assertEqual(first[:2], second[:2])
        self.assertNotEqual(first[2:], second[2:])
        self.assertEqual(len(first), 4)

    def test_quality_filters_do_not_remove_saved_long_tracks(self):
        songs = [dict(track('Long'), duration=3600), dict(track('Short'), duration=20),
                 dict(track('Live'), is_live=True), track('Artist full album'), track('Good')]
        profile = build_profile([track('Saved')], {})
        result = rank_tracks(songs, profile, discovery=True)
        self.assertEqual([t['title'] for t in result], ['Good'])
        self.assertTrue(rank_tracks([songs[0]], build_profile([songs[0]], {})))

    def test_manual_refresh_exposure_demotes_previously_shown_tracks(self):
        songs = [track('Alternative ' + str(i)) for i in range(8)]
        profile = build_profile([track('Saved')], {})
        first = rank_tracks(songs, profile, discovery=True)
        exposure = {track_key(t): 1 for t in first}
        second = rank_tracks(songs, profile, discovery=True, exposure=exposure)
        self.assertTrue({track_key(t) for t in first}.isdisjoint(track_key(t) for t in second))

    def test_malformed_history_is_ignored_without_losing_saved_songs(self):
        profile = build_profile([track('Saved')], {'bad': {'track': track('Bad'), 'plays': float('nan'), 'last_played': 1}})
        self.assertEqual(len(profile.known), 1)

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
    def test_home_excludes_queued_tracks_and_fills_offline_slots(self):
        player = FakePlayer()
        songs = [track(str(i), 'Artist ' + str(i)) for i in range(10)]
        player._base_queue, player._priority_queue = [songs[0]], [songs[1]]
        manager = RecommendationManager(player, None, MagicMock(entries={}))
        self.addCleanup(manager.shutdown)
        manager._profile = build_profile(songs, {})
        emitted = []
        manager.updated.connect(emitted.append)
        manager._publish()
        self.assertEqual(len(emitted[-1]), 8)
        self.assertFalse({track_key(t) for t in emitted[-1]} & {track_key(t) for t in songs[:2]})

    def test_failed_search_retries_soon_instead_of_caching_failure_for_half_hour(self):
        manager = RecommendationManager(FakePlayer(), None, MagicMock(entries={}))
        self.addCleanup(manager.shutdown)
        profile = build_profile([track('Saved')], {})
        manager._make_profile = lambda: profile
        manager._fingerprint = tuple(discovery_seeds(profile, manager._rotation))
        manager._last_fetch, manager._had_error = 100, True
        with patch('core.recommendations.time.monotonic', return_value=161), patch('core.recommendations.SearchWorker') as search:
            manager.refresh()
            search.assert_called_once()
            self.assertEqual(search.call_args.kwargs['result_limit'], 12)

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
