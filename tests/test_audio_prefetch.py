import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from core.audio_prefetch import AudioPrefetcher, PrefetchWorker, cache_key
from core.player import MusicPlayer

app = QApplication.instance() or QApplication([])


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = AudioPrefetcher(directory=self.temp.name)
        self.addCleanup(self.cache.shutdown)

    def save(self, url, data=b'audio'):
        path = Path(self.temp.name) / (cache_key(url) + '.webm')
        path.write_bytes(data)
        return str(path)

    def test_cached_request_does_not_start_download(self):
        url = 'https://example.com/song'
        path = self.save(url)
        with patch('core.audio_prefetch.PrefetchWorker') as worker:
            self.cache.request(url)
            worker.assert_not_called()
        self.assertEqual(self.cache.state, 'ready')
        self.assertEqual(self.cache.cached_path(url), path)

    def test_local_files_are_not_downloaded(self):
        with patch('core.audio_prefetch.PrefetchWorker') as worker:
            self.cache.request('/tmp/song.wav')
            worker.assert_not_called()
        self.assertEqual(self.cache.state, 'idle')

    def test_empty_or_missing_files_are_not_reused(self):
        url = 'https://example.com/song'
        self.save(url, b'')
        self.assertIsNone(self.cache.cached_path(url))
        self.assertIsNone(self.cache.cached_path('missing'))

    def test_queue_change_cancels_previous_request(self):
        with patch('core.audio_prefetch.PrefetchWorker') as factory:
            worker = factory.return_value
            worker.url = 'https://example.com/first'
            self.cache.request(worker.url)
            self.cache.request('https://example.com/second')
            worker.requestInterruption.assert_called_once()
            self.assertEqual(self.cache._wanted, 'https://example.com/second')
            self.cache._finished()
            self.assertEqual(factory.call_count, 2)

    def test_failure_is_throttled_and_does_not_block_playback(self):
        url = 'https://example.com/song'
        self.cache._failed(url)
        with patch('core.audio_prefetch.PrefetchWorker') as worker:
            self.cache.request(url)
            worker.assert_not_called()
        self.assertEqual(self.cache.state, 'unavailable')
        self.assertIsNone(self.cache.cached_path(url))

    def test_late_result_does_not_change_status_for_new_queue(self):
        self.cache._wanted = 'https://example.com/new'
        self.cache._ready('https://example.com/old', '/tmp/old')
        self.assertEqual(self.cache.state, 'idle')

    def test_cache_pruning_preserves_current_track(self):
        urls = ['https://example.com/' + str(i) for i in range(5)]
        paths = [self.save(url) for url in urls]
        for i, path in enumerate(paths):
            os.utime(path, (100 + i, 100 + i))
        self.cache._protected = {cache_key(urls[0])}
        self.cache.prune()
        self.assertTrue(Path(paths[0]).exists())
        self.assertFalse(Path(paths[1]).exists())

    def test_worker_installs_complete_download_and_removes_partial_directory(self):
        url = 'https://example.com/song'
        worker = PrefetchWorker(url, self.temp.name)
        results = []
        worker.ready.connect(lambda *args: results.append(args))
        def fake_download(worker, command, timeout):
            template = Path(command[command.index('--output') + 1])
            audio = template.parent / 'audio.webm'
            audio.write_bytes(b'completed audio')
            return subprocess.CompletedProcess(command, 0, str(audio) + '\n', '')
        with patch('core.audio_prefetch.run_extractor', side_effect=fake_download):
            worker.run()
        self.assertEqual(len(results), 1)
        self.assertEqual(Path(results[0][1]).read_bytes(), b'completed audio')
        self.assertFalse(list(Path(self.temp.name).glob('.download-*')))

    def test_worker_never_accepts_file_outside_its_download_directory(self):
        worker = PrefetchWorker('https://example.com/song', self.temp.name)
        outside = Path(self.temp.name) / 'outside.webm'
        outside.write_bytes(b'outside')
        results, errors = [], []
        worker.ready.connect(lambda *args: results.append(args))
        worker.failed.connect(errors.append)
        with patch('core.audio_prefetch.run_extractor', return_value=subprocess.CompletedProcess([], 0, str(outside), '')):
            worker.run()
        self.assertFalse(results)
        self.assertEqual(len(errors), 1)
        self.assertTrue(outside.exists())


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        patcher = patch('core.player.mpv.MPV', side_effect=[MagicMock(), MagicMock()])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.player = MusicPlayer()
        self.addCleanup(self.player.shutdown)
        self.player.prefetcher.request = MagicMock()

    def song(self, title):
        return {'title': title, 'url': 'https://example.com/' + title}

    def test_next_track_download_begins_from_actual_queue_order(self):
        p = self.player
        p.play_queue([self.song('A'), self.song('B')])
        p._prepare_next()
        self.assertEqual(p.prefetcher.request.call_args.args[0], self.song('B')['url'])
        p.add_to_queue(self.song('Priority'), play_next=True)
        p._prepare_next()
        self.assertEqual(p.prefetcher.request.call_args.args[0], self.song('Priority')['url'])

    def test_cached_file_is_used_for_regular_playback(self):
        p = self.player
        p.prefetcher.cached_path = MagicMock(return_value='/tmp/prepared.webm')
        p.play_url('https://example.com/song')
        p.mpv.play.assert_called_with('/tmp/prepared.webm')

    def test_cache_miss_uses_original_online_source(self):
        p = self.player
        p.prefetcher.cached_path = MagicMock(return_value=None)
        p.play_url('https://example.com/song')
        p.mpv.play.assert_called_with('https://example.com/song')

    def test_crossfade_uses_prepared_file(self):
        p = self.player
        p.play_queue([self.song('A'), self.song('B')])
        p.prefetcher.cached_path = MagicMock(return_value='/tmp/prepared.webm')
        p._start_crossfade(3)
        p.mpv.play.assert_called_with('/tmp/prepared.webm')

    def test_stopped_player_does_not_restart_background_download(self):
        p = self.player
        p.play_queue([self.song('A'), self.song('B')])
        p.stop()
        p._prepare_next()
        self.assertEqual(p.prefetcher.request.call_args.args[0], '')

    def test_disabled_setting_cancels_preparation(self):
        p = self.player
        p.play_queue([self.song('A'), self.song('B')])
        p.theme_manager = MagicMock(current_theme={'PREFETCH_ENABLED': False})
        p._prepare_next()
        self.assertEqual(p.prefetcher.request.call_args.args[0], '')

    def test_shuffle_repeat_prepares_the_same_track_that_will_play(self):
        p = self.player
        p.play_queue([self.song('A'), self.song('B'), self.song('C')])
        p.toggle_shuffle()
        p.toggle_repeat()
        p._shuffled_indices.clear()
        prepared = p._get_next_track_info()[0]
        played = p._pop_next_track()[0]
        self.assertEqual(prepared['url'], played['url'])
