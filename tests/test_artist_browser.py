import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import subprocess
import unittest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from core.artist_browser import ArtistWorker, channel_url, PAGE_SIZE
from core.search_engine import SearchWorker, PlaylistImportWorker
from core.i18n import language_manager
from ui.artist_page import ArtistPage
from ui.artist_button import ArtistButton
from ui.search_page import SearchResultCard
from ui.playlist_page import PlaylistTrackCard
from ui.queue_page import QueueTrackCard

app = QApplication.instance() or QApplication([])
TRACK = {'title': 'A song', 'uploader': 'A musician',
         'url': 'https://www.youtube.com/watch?v=abc',
         'channel_url': 'https://www.youtube.com/@musician', 'platform': 'YouTube Music'}


def response(data):
    return subprocess.CompletedProcess([], 0, json.dumps(data), '')


class ArtistWorkerTests(unittest.TestCase):
    def test_channel_urls_are_normalized_and_reject_other_hosts(self):
        self.assertEqual(channel_url(TRACK), 'https://www.youtube.com/@musician/videos')
        self.assertEqual(channel_url({'uploader_url': 'https://soundcloud.com/artist'}),
                         'https://soundcloud.com/artist/tracks')
        self.assertEqual(channel_url({'channel_id': 'UC' + 'a' * 22}),
                         'https://www.youtube.com/channel/UC' + 'a' * 22 + '/videos')
        self.assertEqual(channel_url({'channel_url': 'https://youtube.com.example.org/@artist'}), '')
        self.assertEqual(channel_url({'channel_url': 'file:///tmp/channel'}), '')

    def test_search_and_import_retain_channel_identity(self):
        data = dict(TRACK, uploader_id='@musician', channel_id='UC' + 'a' * 22)
        for worker, signal_name in ((SearchWorker('musician', ['YouTube Music']), 'results_ready'),
                                    (PlaylistImportWorker(TRACK['url']), 'import_finished')):
            results = []
            getattr(worker, signal_name).connect(results.extend)
            with patch('core.search_engine.run_extractor', return_value=response(data)):
                worker.run()
            self.assertEqual(results[0]['channel_url'], TRACK['channel_url'])
            self.assertEqual(results[0]['channel_id'], data['channel_id'])

    def test_browses_channel_with_bounds_and_filters_unavailable_and_duplicates(self):
        worker = ArtistWorker(TRACK, offset=30)
        tracks, source = [], []
        worker.results_ready.connect(tracks.extend)
        worker.source_ready.connect(source.append)
        entries = [TRACK, TRACK, dict(TRACK, availability='private'), None,
                   {'url': 'https://www.youtube.com/@another', '_type': 'playlist'}]
        with patch('core.artist_browser.run_extractor', return_value=response({'entries': entries})) as run:
            worker.run()
        args = run.call_args.args[1]
        self.assertEqual(args[-1], 'https://www.youtube.com/@musician/videos')
        self.assertEqual(args[args.index('--playlist-start') + 1], '31')
        self.assertEqual(args[args.index('--playlist-end') + 1], '60')
        self.assertEqual(len(tracks), 1)
        self.assertFalse(source[0]['fallback'])
        self.assertFalse(worker.has_more)

    def test_old_track_resolves_channel_from_video_before_browsing(self):
        old = {key: value for key, value in TRACK.items() if key != 'channel_url'}
        worker = ArtistWorker(old)
        results = []
        worker.results_ready.connect(results.extend)
        with patch('core.artist_browser.run_extractor', side_effect=[response(TRACK), response({'entries': [TRACK]})]) as run:
            worker.run()
        self.assertIn('--no-playlist', run.call_args_list[0].args[1])
        self.assertEqual(run.call_args_list[1].args[1][-1], 'https://www.youtube.com/@musician/videos')
        self.assertEqual(results[0]['channel_url'], TRACK['channel_url'])

    def test_missing_channel_falls_back_to_labelled_platform_search(self):
        worker = ArtistWorker({'uploader': 'An artist', 'platform': 'SoundCloud'})
        sources = []
        worker.source_ready.connect(sources.append)
        with patch('core.artist_browser.run_extractor', return_value=response({'entries': []})) as run:
            worker.run()
        self.assertEqual(run.call_args.args[1][-1], 'scsearch30:An artist')
        self.assertTrue(sources[0]['fallback'])
        self.assertFalse(worker.has_more)

    def test_error_and_cancellation_do_not_report_success(self):
        for error, expected_errors in ((ValueError('no response'), 1), (InterruptedError(), 0)):
            worker = ArtistWorker(TRACK)
            errors, results = [], []
            worker.search_error.connect(errors.append)
            worker.results_ready.connect(results.append)
            with patch('core.artist_browser.run_extractor', side_effect=error):
                worker.run()
            self.assertEqual(len(errors), expected_errors)
            self.assertFalse(results)

    def test_full_page_has_more(self):
        worker = ArtistWorker(TRACK)
        with patch('core.artist_browser.run_extractor', return_value=response({'entries': [TRACK] * PAGE_SIZE})):
            worker.run()
        self.assertTrue(worker.has_more)


class ManualWorker(QObject):
    results_ready = pyqtSignal(list)
    source_ready = pyqtSignal(dict)
    search_error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, track, offset=0, parent=None):
        super().__init__(parent)
        self.track, self.offset = dict(track), offset
        self.has_more = False
        self.running = False
        self.cancelled = False

    def start(self):
        self.running = True

    def isRunning(self):
        return self.running

    def requestInterruption(self):
        self.cancelled = True

    def wait(self):
        self.running = False

    def complete(self, tracks, has_more=False):
        self.has_more = has_more
        self.results_ready.emit(tracks)
        self.running = False
        self.finished.emit()


class ArtistPageTests(unittest.TestCase):
    def setUp(self):
        self.patch = patch('ui.artist_page.ArtistWorker', ManualWorker)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.player = MagicMock()
        self.page = ArtistPage(self.player)
        self.addCleanup(self.page.close)
        self.addCleanup(self.page.shutdown)
        self.addCleanup(lambda: language_manager.set_language('pl', persist=False))

    def test_navigation_does_not_play_and_stale_responses_are_ignored(self):
        self.page.open_artist(TRACK)
        old = self.page._current_worker
        self.page.open_artist(dict(TRACK, uploader='Second artist'))
        current = self.page._current_worker
        self.assertTrue(old.cancelled)
        old.source_ready.emit({'track': TRACK, 'fallback': False, 'url': TRACK['channel_url']})
        old.complete([TRACK])
        self.assertEqual(self.page.artist_title.text(), 'Second artist')
        self.assertEqual(self.page._tracks, [])
        self.assertIs(self.page._current_worker, current)
        self.player.play_queue.assert_not_called()

    def test_pagination_deduplication_and_play_from_selected_position(self):
        self.page.open_artist(TRACK)
        self.page._current_worker.complete([TRACK], has_more=True)
        self.page.more.click()
        self.assertEqual(self.page._current_worker.offset, 30)
        second = dict(TRACK, url='https://www.youtube.com/watch?v=second', title='Second song')
        self.page._current_worker.complete([TRACK, second])
        self.assertEqual(len(self.page._tracks), 2)
        self.assertTrue(self.page.more.isHidden())
        self.player.play_queue.assert_not_called()
        self.page._on_result_clicked(second)
        self.player.play_queue.assert_called_once_with([TRACK, second], 1)
        self.page.play_all.click()
        self.player.play_queue.assert_called_with([TRACK, second], 0)

    def test_failed_page_can_retry_without_losing_tracks(self):
        self.page.open_artist(TRACK)
        self.page._current_worker.complete([TRACK], has_more=True)
        self.page.more.click()
        failed = self.page._current_worker
        failed.search_error.emit('Nie udało się wczytać kanału. Sprawdź połączenie i spróbuj ponownie.')
        failed.running = False
        failed.finished.emit()
        self.assertEqual(self.page._tracks, [TRACK])
        self.assertFalse(self.page.retry.isHidden())
        self.page.retry.click()
        self.assertEqual(self.page._current_worker.offset, 30)

    def test_artist_buttons_never_trigger_track_playback(self):
        for card, play_signal in ((SearchResultCard(TRACK), 'clicked'),
                                  (PlaylistTrackCard(TRACK, 0), 'play_clicked'),
                                  (QueueTrackCard(TRACK, 0), 'play_clicked')):
            played, artists = [], []
            getattr(card, play_signal).connect(played.append)
            card.artist_requested.connect(artists.append)
            card.show()
            button = card.findChild(ArtistButton)
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
            self.assertEqual(artists, [TRACK])
            self.assertEqual(played, [])
            card.close()

    def test_new_interface_translates_live_but_artist_name_is_unchanged(self):
        self.page.open_artist(dict(TRACK, uploader='Ustawienia'))
        language_manager.set_language('en', persist=False)
        self.assertEqual(self.page.artist_title.text(), 'Ustawienia')
        self.assertEqual(self.page.more.text(), 'Show more')
        self.assertEqual(self.page.status_label.text(), 'Loading artist tracks…')
        self.assertEqual(self.page.play_all.text(), 'Play all')
