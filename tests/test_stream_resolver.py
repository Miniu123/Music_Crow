import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtTest import QTest

from core import stream_resolver as sr
from core.player import MusicPlayer

app = QCoreApplication.instance() or QCoreApplication([])
YT = 'https://www.youtube.com/watch?v=abcdefghijk'
YT_MUSIC = 'https://music.youtube.com/watch?v=abcdefghijk'
STREAM = 'https://rr1.googlevideo.com/videoplayback?expire=%d&itag=251'


def stream_info(expires_in=6 * 3600, available_at=0):
    url = STREAM % (time.time() + expires_in)
    return {'url': url, 'headers': {'User-Agent': 'UA/1', 'Accept-Language': 'en'},
            'expires': sr.stream_expiry(url), 'protocol': 'https', 'available_at': available_at}


def wait_for(condition, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QTest.qWait(10)
        if condition():
            return True
    return condition()


class ResolverTests(unittest.TestCase):
    def make(self, extractor, workers=1):
        resolver = sr.StreamResolver(extractor=extractor, workers=workers)
        self.addCleanup(resolver.shutdown)
        results = []
        resolver.resolved.connect(lambda url, info, play: results.append((url, info, play)))
        return resolver, results

    def test_supported_hosts_only(self):
        self.assertTrue(sr.is_resolvable(YT))
        self.assertTrue(sr.is_resolvable('https://soundcloud.com/artist/track'))
        self.assertFalse(sr.is_resolvable('https://example.com/song'))
        self.assertFalse(sr.is_resolvable('https://youtube.com.evil.example/watch?v=x'))
        self.assertFalse(sr.is_resolvable('/home/user/song.webm'))

    def test_click_lookup_runs_once_in_fast_mode_and_is_cached(self):
        calls, gate = [], threading.Event()
        def extractor(url, fast=False):
            calls.append(fast)
            gate.wait(2)
            return stream_info()
        resolver, results = self.make(extractor)
        self.assertTrue(resolver.play_now(YT))
        self.assertTrue(resolver.play_now(YT_MUSIC))  # same video: joins the running lookup
        gate.set()
        self.assertTrue(wait_for(lambda: results))
        self.assertEqual(calls, [True])
        self.assertTrue(results[0][2])
        self.assertIsNotNone(resolver.usable(YT_MUSIC))
        self.assertFalse(resolver.play_now(YT))  # usable now: nothing to wait for

    def test_click_is_not_queued_behind_background_lookups(self):
        gate = threading.Event()
        def extractor(url, fast=False):
            if not fast:
                gate.wait(3)  # background lookups are stuck
            return stream_info()
        resolver, results = self.make(extractor, workers=1)
        resolver.prefetch(['https://www.youtube.com/watch?v=background1',
                           'https://www.youtube.com/watch?v=background2'])
        resolver.play_now(YT)
        self.assertTrue(wait_for(lambda: any(play for _, _, play in results), timeout=1))
        gate.set()

    def test_background_lookups_use_quality_mode_newest_first(self):
        gate, order = threading.Event(), []
        def extractor(url, fast=False):
            gate.wait(2)
            order.append((url[-1], fast))
            return stream_info()
        resolver, results = self.make(extractor, workers=1)
        resolver.prefetch(['https://www.youtube.com/watch?v=aaaaaaaaaa1'])
        self.assertTrue(wait_for(lambda: resolver._prefetching))  # first one is running
        resolver.prefetch(['https://www.youtube.com/watch?v=aaaaaaaaaa2',
                           'https://www.youtube.com/watch?v=aaaaaaaaaa3'])
        gate.set()
        self.assertTrue(wait_for(lambda: len(results) == 3))
        self.assertEqual(order, [('1', False), ('3', False), ('2', False)])

    def test_expired_streams_are_not_reused(self):
        resolver, results = self.make(lambda url, fast=False: stream_info(expires_in=60))
        resolver.play_now(YT)
        self.assertTrue(wait_for(lambda: results))
        self.assertIsNone(resolver.cached(YT))  # expires within the safety margin

    def test_failed_click_backs_off_and_reports_none(self):
        def broken(url, fast=False):
            raise RuntimeError('unavailable')
        resolver, results = self.make(broken)
        resolver.play_now(YT)
        self.assertTrue(wait_for(lambda: results))
        self.assertIsNone(results[0][1])
        self.assertFalse(resolver.play_now(YT))  # recently failed: play through mpv instead

    def test_waiting_stream_is_cached_but_not_usable_yet(self):
        resolver, results = self.make(lambda url, fast=False: stream_info(available_at=time.time() + 0.3))
        resolver.prefetch([YT])
        self.assertTrue(wait_for(lambda: results))  # the worker did not sleep on it
        self.assertIsNotNone(resolver.cached(YT))
        self.assertIsNone(resolver.usable(YT))
        self.assertTrue(wait_for(lambda: resolver.usable(YT) is not None))

    def test_audio_stream_prefers_audio_only_formats(self):
        info = {'requested_formats': [{'vcodec': 'avc1', 'url': 'video'},
                                      {'vcodec': 'none', 'url': STREAM % 2000000000, 'http_headers': {'A': 'b'}}],
                'available_at': 123}
        stream = sr._audio_stream(info)
        self.assertEqual(stream['headers'], {'A': 'b'})
        self.assertEqual(stream['expires'], 2000000000)
        self.assertEqual(stream['available_at'], 123)
        self.assertIsNone(sr._audio_stream({'is_live': True, 'url': 'x'}))

    def run_clients(self, behaviour, url=YT, fast=True):
        """Embedded runs in-process (fake yt_dlp); other clients via run_extractor."""
        import json, subprocess
        tried = []
        class FakeYDL:
            def __init__(self, options):
                self.client = options['extractor_args']['youtube']['player_client'][0]
            def extract_info(self, url, download):
                tried.append(self.client)
                result = behaviour[self.client]
                if isinstance(result, Exception):
                    raise result
                return result
        def fake_run(worker, command, timeout):
            client = 'android' if 'youtube:player_client=android' in command else 'default'
            tried.append(client)
            result = behaviour[client]
            if isinstance(result, Exception):
                return subprocess.CompletedProcess(command, 1, '', str(result))
            return subprocess.CompletedProcess(command, 0, json.dumps(result), '')
        # Patch the factory itself so a background warm-up can never swap in real yt-dlp.
        with patch.object(sr, '_youtube_dl', side_effect=lambda profile: FakeYDL(sr.PROFILES[profile])), \
                patch('core.search_engine.run_extractor', side_effect=fake_run):
            return sr.extract_stream(url, fast=fast), sorted(tried)

    def test_click_uses_embedded_audio_when_it_works_at_once(self):
        stream, tried = self.run_clients({'web_embedded': {'url': STREAM % 2000000000, 'vcodec': 'none'},
                                          'android': {'url': 'https://android/stream'}})
        self.assertIn('googlevideo', stream['url'])
        self.assertTrue(stream['audio_only'])
        self.assertEqual(tried, ['android', 'web_embedded'])  # asked concurrently

    def test_click_on_embed_blocked_video_starts_with_android_stream(self):
        waiting = {'url': STREAM % 2000000000, 'available_at': time.time() + 5}
        stream, _ = self.run_clients({'web_embedded': waiting, 'android': {'url': 'https://android/stream'}})
        self.assertEqual(stream['url'], 'https://android/stream')

    def test_background_lookup_keeps_quality_and_soundcloud_uses_default(self):
        stream, tried = self.run_clients({'web_embedded': RuntimeError('blocked'),
                                          'default': {'url': STREAM % 2000000000}}, fast=False)
        self.assertEqual(tried, ['default', 'web_embedded'])
        _, tried = self.run_clients({'default': {'url': 'https://sc/stream'}}, url='https://soundcloud.com/a/b')
        self.assertEqual(tried, ['default'])

    def test_fallback_clients_never_run_inside_the_app_process(self):
        # Running another YouTube client in-process made the embedded client
        # return HLS video manifests afterwards; fallbacks must use a subprocess.
        self.assertEqual(set(sr.PROFILES), {'embedded'})
        self.assertEqual(set(sr.ISOLATED_CLIENTS), {'android', 'default'})


class PlayerStreamTests(unittest.TestCase):
    def setUp(self):
        patcher = patch('core.player.mpv.MPV', side_effect=[MagicMock(), MagicMock()])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.player = MusicPlayer()
        self.addCleanup(self.player.shutdown)
        self.player.prefetcher.request = MagicMock()
        self.player.prefetcher.cached_path = MagicMock(return_value=None)
        self.player.resolver.play_now = MagicMock(return_value=True)

    def test_click_waits_for_stream_then_plays_it_with_headers(self):
        p = self.player
        p.play_url(YT)
        p.mpv.play.assert_not_called()
        p.mpv.command.assert_called_with('stop')  # previous track is silenced meanwhile
        info = stream_info()
        p._on_stream_resolved(YT_MUSIC, info)  # result may arrive under another URL form
        p.mpv.play.assert_called_with(info['url'])
        self.assertEqual(p.mpv.user_agent, 'UA/1')
        self.assertEqual(p.mpv.http_header_fields, ['Accept-Language: en'])

    def test_cached_stream_plays_immediately(self):
        p = self.player
        info = stream_info()
        p.resolver.usable = MagicMock(return_value=info)
        p.play_url(YT)
        p.mpv.play.assert_called_with(info['url'])

    def test_failed_lookup_falls_back_to_mpv(self):
        p = self.player
        p.play_url(YT)
        p._on_stream_resolved(YT, None)
        p.mpv.play.assert_called_with(YT)

    def test_background_result_that_must_wait_does_not_end_the_click(self):
        p = self.player
        p.play_url(YT)
        p._on_stream_resolved(YT, stream_info(available_at=time.time() + 5), False)
        p.mpv.play.assert_not_called()
        self.assertIsNotNone(p._pending_play)
        info = stream_info()
        p._on_stream_resolved(YT, info, True)
        p.mpv.play.assert_called_with(info['url'])

    def test_stale_result_is_ignored(self):
        p = self.player
        p.play_url(YT)
        p.play_url('https://www.youtube.com/watch?v=newertrack0')
        p._on_stream_resolved(YT, stream_info())
        p.mpv.play.assert_not_called()

    def test_idle_while_resolving_does_not_skip_the_track(self):
        p = self.player
        ended = []
        p.track_ended.connect(lambda: ended.append(True))
        p._current_track = {'url': YT}
        p.play_url(YT)
        p.mpv.idle_active = False
        p._poll_mpv_state()
        p.mpv.idle_active = True
        p._poll_mpv_state()
        self.assertEqual(ended, [])

    def test_upcoming_tracks_are_resolved_in_advance(self):
        p = self.player
        p.resolver.prefetch = MagicMock()
        tracks = [{'title': t, 'url': f'https://www.youtube.com/watch?v={t * 11}'} for t in 'ABC']
        p.play_queue(tracks)
        p._prepare_next()
        urls = p.resolver.prefetch.call_args.args[0]
        self.assertEqual(urls[:2], [tracks[1]['url'], tracks[2]['url']])


if __name__ == '__main__':
    unittest.main()
