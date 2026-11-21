import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0,str(Path(__file__).parents[1]/'app/src/main/python'))
import sources

class SourceTests(unittest.TestCase):
    def test_non_source_links_never_reach_extractor(self):
        with patch.object(sources.yt_dlp,'YoutubeDL') as extractor:
            for url in ('http://youtube.com/watch?v=x','https://example.com/file','https://user:password@youtube.com/watch?v=x','file:///etc/passwd'):
                with self.assertRaises(ValueError):sources.resolve(url)
            extractor.assert_not_called()

    def test_older_track_falls_back_to_artist_search_after_extractor_failure(self):
        with patch.object(sources.yt_dlp,'YoutubeDL') as factory, patch.object(sources,'search',return_value='{"tracks": []}') as search:
            factory.return_value.__enter__.return_value.extract_info.side_effect=sources.yt_dlp.utils.DownloadError('unavailable')
            result=json.loads(sources.browse(json.dumps({'url':'https://youtu.be/abc','uploader':'Artist'})))
            self.assertTrue(result['fallback'])
            search.assert_called_once_with('Artist','YouTube Music')

    def test_playlist_larger_than_supported_limit_is_not_silently_truncated(self):
        with patch.object(sources,'extract_list',return_value={'tracks':[{}]*10001,'more':False}):
            with self.assertRaises(ValueError):sources.import_playlist('https://www.youtube.com/playlist?list=abc')

    def test_channel_browsing_retains_offset(self):
        with patch.object(sources,'extract_list',return_value={'tracks':[],'more':False}) as extract:
            sources.browse(json.dumps({'channel_url':'https://www.youtube.com/@artist','url':'https://youtu.be/abc'}),30)
            extract.assert_called_once_with('https://www.youtube.com/@artist/videos','YouTube Music',30)

    def test_discovery_search_excludes_remixes_unless_explicitly_allowed(self):
        with patch.object(sources, 'search', return_value='{"tracks": []}') as search:
            sources.discover('Artist', 'YouTube Music', False)
            self.assertIn('-remix', search.call_args.args[0])
            self.assertIn('official audio', search.call_args.args[0])
            sources.discover('Artist', 'YouTube Music', True)
            self.assertNotIn('-remix', search.call_args.args[0])
            sources.discover('Artist', 'SoundCloud', False)
            search.assert_called_with('Artist', 'SoundCloud')

    def test_ytmusic_watch_link_imports_whole_playlist_in_order(self):
        data = {'tracks': [{'title': 'First'}, {'title': 'Second'}], 'title': 'My mix', 'more': False, 'skipped': 1}
        with patch.object(sources, 'extract_list', return_value=data) as extract:
            result = json.loads(sources.import_playlist('https://music.youtube.com/watch?v=selected&list=PL_example123&index=4&si=share'))
            extract.assert_called_once_with('https://www.youtube.com/playlist?list=PL_example123', 'YouTube Music', count=10001)
            self.assertEqual(result, data)

    def test_invalid_or_account_only_playlists_never_reach_extractor(self):
        links = ['https://music.youtube.com/watch?v=only_song',
                 'https://example.com/playlist?list=PL_abc',
                 'https://music.youtube.com/playlist?list=LM',
                 'https://music.youtube.com/playlist?list=RDAMVM_radio']
        with patch.object(sources, 'extract_list') as extract:
            for link in links:
                with self.assertRaises(ValueError): sources.import_playlist(link)
            extract.assert_not_called()

    def test_empty_playlist_is_not_imported_as_a_song(self):
        with patch.object(sources.yt_dlp, 'YoutubeDL') as factory:
            factory.return_value.__enter__.return_value.extract_info.return_value = {
                'title': 'Empty', 'webpage_url': 'https://www.youtube.com/playlist?list=PL_abc', 'entries': []}
            with self.assertRaisesRegex(ValueError, 'pusta'): sources.import_playlist('https://music.youtube.com/playlist?list=PL_abc')

    def test_unavailable_playlist_items_report_skipped_count(self):
        with patch.object(sources.yt_dlp, 'YoutubeDL') as factory:
            factory.return_value.__enter__.return_value.extract_info.return_value = {
                'title': 'Mixed', 'entries': [None,
                    {'title': '[Private video]', 'url': 'https://youtu.be/private'},
                    {'title': 'Available', 'url': 'https://youtu.be/available'}]}
            result = json.loads(sources.import_playlist('https://music.youtube.com/playlist?list=PL_abc'))
            self.assertEqual(result['skipped'], 2)
            self.assertEqual([t['title'] for t in result['tracks']], ['Available'])

    def test_soundcloud_metadata_is_portable(self):
        result=sources.track({'webpage_url':'https://soundcloud.com/artist/song','title':'Song','uploader':'Artist','uploader_url':'https://soundcloud.com/artist','duration':120,'thumbnails':[{'url':'https://example.com/cover.jpg'}]},'SoundCloud')
        self.assertEqual(result['uploader_url'],'https://soundcloud.com/artist')
        self.assertEqual(result['platform'],'SoundCloud')
        self.assertEqual(result['thumbnail_url'],'https://example.com/cover.jpg')

if __name__=='__main__':unittest.main()
