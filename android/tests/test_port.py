import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'app/src/main/python'))
import crow
from recommendations import build_profile, rank_tracks, track_key


def track(title='Song', url='https://www.youtube.com/watch?v=abc', artist='Artist'):
    return dict(title=title, url=url, uploader=artist, duration=180, platform='YouTube Music')


class PortableLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        crow.initialize(self.root)

    def call(self, action, **args):
        return json.loads(crow.dispatch(action, json.dumps(args)))

    def sample(self):
        snapshot = crow.initial()
        snapshot['playlists']['Favourite'] = dict(tracks=[track()], cover='')
        snapshot['history']['youtube:abc'] = dict(track=track(), plays=4, last_played=100)
        return snapshot

    def test_old_android_library_is_migrated_without_deleting_original(self):
        (self.root / 'music-crow-android.json').unlink()
        old = self.root / 'library.json'
        old.write_text(json.dumps([track()]))
        crow.initialize(self.root)
        self.assertEqual(self.call('state')['playlists']['Z telefonu']['tracks'][0]['title'], 'Song')
        self.assertTrue(old.exists())

    def test_playlist_duplicate_youtube_urls_and_restart(self):
        self.call('create', name='Music')
        self.call('add', name='Music', tracks=[track(), track(url='https://youtu.be/abc')])
        crow.initialize(self.root)
        self.assertEqual(len(self.call('state')['playlists']['Music']['tracks']), 1)

    def test_new_import_does_not_merge_with_existing_playlist(self):
        self.call('add', name='Existing', tracks=[track()])
        with self.assertRaises(ValueError):
            self.call('add', name='Existing', tracks=[track(url='https://youtu.be/new')], new_only=True)
        self.assertEqual(len(self.call('state')['playlists']['Existing']['tracks']), 1)
        self.call('add', name='Imported', tracks=[track(url='https://youtu.be/first'), track(url='https://youtu.be/second')], new_only=True)
        crow.initialize(self.root)
        self.assertEqual([t['url'] for t in self.call('state')['playlists']['Imported']['tracks']],
                         ['https://youtu.be/first', 'https://youtu.be/second'])

    def test_restore_merges_collisions_and_is_idempotent(self):
        self.call('add', name='Favourite', tracks=[track(title='Existing', url='https://youtu.be/existing')])
        self.call('restore', snapshot=self.sample())
        self.call('restore', snapshot=self.sample())
        playlists = self.call('state')['playlists']
        self.assertEqual(set(playlists), {'Favourite', 'Favourite (Google Drive)'})
        self.assertEqual(playlists['Favourite']['tracks'][0]['title'], 'Existing')
        self.assertEqual(len(list((self.root / 'recovery').glob('*.json'))), 2)

    def test_history_merge_never_doubles_plays(self):
        self.call('restore', snapshot=self.sample())
        incoming = self.sample()
        incoming['history']['youtube:abc'].update(plays=2, last_played=200)
        self.call('restore', snapshot=incoming)
        item = self.call('state')['history']['youtube:abc']
        self.assertEqual(item['plays'], 4)
        self.assertEqual(item['last_played'], 200)

    def test_history_opt_in_and_credentials_excluded(self):
        self.call('restore', snapshot=self.sample())
        self.assertEqual(self.call('backup')['history'], {})
        self.assertTrue(self.call('backup', history=True)['history'])
        self.assertEqual(set(self.call('backup')), {'format', 'version', 'created_at', 'settings', 'playlists', 'history'})

    def test_unchanged_backup_is_stable(self):
        self.call('add', name='Music', tracks=[track()])
        self.assertEqual(crow.dispatch('backup'), crow.dispatch('backup'))

    def test_invalid_restore_does_not_touch_disk_or_memory(self):
        previous = (self.root / 'music-crow-android.json').read_bytes()
        for invalid in ({}, dict(self.sample(), version=2), dict(self.sample(), history={'bad': {'plays':float('nan')}})):
            with self.assertRaises((ValueError, KeyError)):
                self.call('restore', snapshot=invalid)
            self.assertEqual(previous, (self.root / 'music-crow-android.json').read_bytes())

    def test_atomic_failure_preserves_disk_and_memory(self):
        old = self.call('state')
        replace = crow.os.replace
        def fail(source, target):
            if Path(target).name == 'music-crow-android.json': raise OSError('Disk full')
            return replace(source, target)
        with patch.object(crow.os, 'replace', side_effect=fail):
            with self.assertRaises(OSError): self.call('restore', snapshot=self.sample())
        self.assertEqual(old, self.call('state'))
        self.assertEqual(old, json.loads((self.root / 'music-crow-android.json').read_bytes()))
        self.assertEqual(len(list((self.root / 'recovery').glob('*.json'))), 1)

    def test_corrupt_library_not_overwritten(self):
        target = self.root / 'music-crow-android.json'
        target.write_text('{bad')
        with self.assertRaises(ValueError): crow.initialize(self.root)
        with self.assertRaises(ValueError): self.call('create', name='Oops')
        self.assertEqual(target.read_text(), '{bad')

    def test_reorder_and_rename_preserve_tracks(self):
        self.call('add', name='A', tracks=[track(), track('Second','https://youtu.be/second')])
        self.call('move', name='A', **{'from':0,'to':1})
        self.call('rename', name='A', new='B')
        self.assertEqual(self.call('state')['playlists']['B']['tracks'][0]['title'],'Second')

    def test_path_traversal_invalid_types_and_oversize_lists_rejected(self):
        for name in ('../escape','bad/name','..','x\x00','a'*181):
            with self.assertRaises(ValueError): self.call('create',name=name)
        for value in (False, 0, {}, []):
            with self.assertRaises(ValueError): crow.clean_track(dict(track(),title=value))
        data=self.sample();data['playlists']['Favourite']['tracks']=[track()]*10001
        with self.assertRaises(ValueError): crow.validate(data)

    def test_recommendations_exclude_active_queue_and_diversify(self):
        songs=[track(str(i),'https://youtu.be/'+str(i),'Artist'+str(i%4)) for i in range(12)]
        self.call('add', name='Music', tracks=songs)
        result=self.call('recommend',excluded=songs[:2])['tracks']
        self.assertTrue(result)
        self.assertFalse({t['url'] for t in songs[:2]} & {t['url'] for t in result})
        for artist in {t['uploader'] for t in result}:
            self.assertLessEqual(sum(t['uploader']==artist for t in result),3)

    def test_desktop_accepts_export_and_android_accepts_desktop_snapshot(self):
        # This integration check runs with the repository's .venv (PyQt6 available).
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
        from core.cloud_backup import validate_snapshot
        self.call('restore',snapshot=self.sample())
        portable=self.call('backup',history=True)
        desktop=validate_snapshot(portable)
        self.assertEqual(crow.validate(desktop), desktop)

if __name__=='__main__': unittest.main()
