import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QColor
from PyQt6.QtCore import QObject, pyqtSignal
from core import gdrive_sync as drive
from core.cloud_backup import collect_snapshot, restore_snapshot, validate_snapshot, encode, atomic_write
from core.i18n import language_manager
from core.theme_manager import ThemeManager
from ui.settings_dialog import SettingsDialog

app = QApplication.instance() or QApplication([])
CLIENT = {'installed': {'client_id': 'test.apps.googleusercontent.com', 'client_secret': 'test-only',
          'auth_uri': 'https://accounts.google.com/o/oauth2/auth', 'token_uri': 'https://oauth2.googleapis.com/token'}}
TRACK = {'url': 'https://www.youtube.com/watch?v=song', 'title': 'Song', 'uploader': 'Artist'}
TOKEN = {'token': 'test-only', 'scopes': drive.SCOPES}


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write('theme.json', {'LANGUAGE': 'en', 'BASS_GAIN': 2})
        self.write('playlists/Favourites.json', {'tracks': [TRACK], 'cover_image': '/private/old/computer/path'})
        self.write('listening_history.json', {'track': {'track': TRACK, 'plays': 3, 'last_played': 123.0}})

    def write(self, path, value):
        atomic_write(self.root / path, encode(value))

    def test_snapshot_contains_only_portable_user_data(self):
        for name in ('credentials.json', 'google_token.json', 'token.json', 'cloud_state.json'):
            self.write(name, {'secret': 'DO_NOT_UPLOAD'})
        snapshot = collect_snapshot(self.root, include_history=False)
        payload = encode(snapshot)
        self.assertNotIn(b'DO_NOT_UPLOAD', payload)
        self.assertNotIn(b'/private/old', payload)
        self.assertEqual(snapshot['history'], {})
        self.assertEqual(snapshot['settings']['LANGUAGE'], 'en')
        self.assertEqual(len(snapshot['playlists']), 1)

    def test_covers_restore_to_destination_device_path(self):
        cover = self.root / 'covers/Favourites.png'
        cover.parent.mkdir()
        image = QImage(16, 16, QImage.Format.Format_RGB32)
        image.fill(QColor('purple'))
        image.save(str(cover))
        snapshot = collect_snapshot(self.root)
        destination = self.root / 'other-device'
        restore_snapshot(destination, snapshot)
        saved = json.loads((destination / 'playlists/Favourites.json').read_text())
        self.assertEqual(saved['cover_image'], str(destination / 'covers/Favourites.png'))
        self.assertFalse(QImage(saved['cover_image']).isNull())

    def test_conflicting_playlist_is_kept_and_recovery_is_created(self):
        snapshot = collect_snapshot(self.root)
        snapshot['playlists']['Favourites']['tracks'][0]['title'] = 'Cloud song'
        snapshot['settings']['LANGUAGE'] = 'pl'
        recovery = restore_snapshot(self.root, snapshot)
        self.assertEqual(json.loads((self.root / 'playlists/Favourites.json').read_text())['tracks'][0]['title'], 'Song')
        self.assertEqual(json.loads((self.root / 'playlists/Favourites (Google Drive).json').read_text())['tracks'][0]['title'], 'Cloud song')
        self.assertEqual(json.loads((self.root / 'theme.json').read_text())['LANGUAGE'], 'pl')
        self.assertEqual(json.loads(recovery.read_text())['settings']['LANGUAGE'], 'en')

    def test_identical_playlist_is_not_duplicated(self):
        restore_snapshot(self.root, collect_snapshot(self.root))
        self.assertEqual(len(list((self.root / 'playlists').glob('*.json'))), 1)

    def test_restoring_the_same_conflict_twice_does_not_duplicate_it(self):
        snapshot = collect_snapshot(self.root)
        snapshot['playlists']['Favourites']['tracks'][0]['title'] = 'Cloud song'
        restore_snapshot(self.root, snapshot)
        restore_snapshot(self.root, snapshot)
        self.assertEqual(len(list((self.root / 'playlists').glob('*.json'))), 2)

    def test_history_merge_does_not_double_count(self):
        snapshot = collect_snapshot(self.root)
        snapshot['history']['track']['plays'] = 4
        snapshot['history']['track']['last_played'] = 125
        restore_snapshot(self.root, snapshot)
        result = json.loads((self.root / 'listening_history.json').read_text())
        self.assertEqual(result['track']['plays'], 4)
        self.assertEqual(result['track']['last_played'], 125)

    def test_rejects_path_traversal_and_bad_settings_before_writing(self):
        original = (self.root / 'theme.json').read_bytes()
        for change in ('path', 'theme', 'track', 'version', 'cover'):
            snapshot = collect_snapshot(self.root)
            if change == 'path': snapshot['playlists']['../../outside'] = {'tracks': []}
            if change == 'theme': snapshot['settings']['ACCENT_COLOR'] = 'red; background: url(file:///tmp/secret)'
            if change == 'track': snapshot['playlists']['Favourites']['tracks'][0]['duration'] = 'invalid'
            if change == 'version': snapshot['version'] = 999
            if change == 'cover': snapshot['playlists']['Favourites']['cover'] = 'invalid base64!'
            with self.assertRaises(ValueError):
                restore_snapshot(self.root, snapshot)
            self.assertEqual((self.root / 'theme.json').read_bytes(), original)

    def test_failed_restore_rolls_back_previous_writes(self):
        snapshot = collect_snapshot(self.root)
        snapshot['playlists']['New'] = {'tracks': [TRACK], 'cover': ''}
        before = (self.root / 'theme.json').read_bytes()
        actual_write = atomic_write
        def fail_theme(path, data):
            if path == self.root / 'theme.json':
                raise OSError('disk failure')
            actual_write(path, data)
        with patch('core.cloud_backup.atomic_write', side_effect=fail_theme):
            with self.assertRaises(OSError):
                restore_snapshot(self.root, snapshot)
        self.assertFalse((self.root / 'playlists/New.json').exists())
        self.assertEqual((self.root / 'theme.json').read_bytes(), before)
        self.assertTrue(list((self.root / 'recovery').glob('*.json')))

    def test_token_and_configuration_writes_are_owner_only(self):
        path = self.root / 'test-token.json'
        atomic_write(path, b'{}')
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)


class ManualWorker(QObject):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    open_browser = pyqtSignal(str)
    finished = pyqtSignal()
    def __init__(self, operation, **kwargs):
        super().__init__(kwargs.get('parent'))
        self.operation = operation
        self.kwargs = kwargs
        self.cancelled = False
    def start(self): pass
    def requestInterruption(self): self.cancelled = True
    def wait(self): pass
    def finish(self, **values):
        self.completed.emit(dict(operation=self.operation, token=TOKEN, **values))
        self.finished.emit()


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        worker_patch = patch.object(drive, 'DriveWorker', ManualWorker)
        worker_patch.start()
        self.addCleanup(worker_patch.stop)
        available = patch.object(drive, 'HAS_GOOGLE_API', True)
        available.start()
        self.addCleanup(available.stop)
        self.manager = drive.GDriveSyncManager(root=self.root)
        self.addCleanup(self.manager.shutdown)

    def connect(self):
        atomic_write(self.manager.client_path, encode(CLIENT))
        self.manager.login()
        self.manager._worker.finish(email='example@example.com')
        self.manager._debounce.stop()

    def test_oauth_config_validation_and_copy(self):
        source = self.root / 'source.json'
        atomic_write(source, encode(CLIENT))
        self.manager.configure(source)
        self.assertTrue(self.manager.has_credentials_file())
        bad = copy.deepcopy(CLIENT)
        bad['installed']['token_uri'] = 'https://untrusted.example/token'
        with self.assertRaises(ValueError): drive.validate_client(bad)
        with self.assertRaises(ValueError): drive.validate_client({'web': CLIENT['installed']})

    def test_login_is_nonblocking_and_persists_session(self):
        self.connect()
        self.assertTrue(self.manager.connected)
        self.assertFalse(self.manager.busy)
        self.assertEqual(self.manager.email, 'example@example.com')
        self.assertEqual(json.loads(self.manager.token_path.read_text()), TOKEN)

    def test_logout_ignores_late_authentication_and_keeps_backups(self):
        atomic_write(self.manager.client_path, encode(CLIENT))
        self.manager.login()
        worker = self.manager._worker
        self.manager.logout()
        worker.finish(email='late@example.com')
        self.assertTrue(worker.cancelled)
        self.assertFalse(self.manager.connected)
        self.assertFalse(self.manager.token_path.exists())
        self.assertTrue(self.manager.client_path.exists())

    def test_upload_changes_are_coalesced_and_identical_data_is_skipped(self):
        self.connect()
        self.manager.sync_now()
        self.assertTrue(self.manager.busy)
        worker = self.manager._worker
        self.manager.sync_now()
        self.assertIs(self.manager._worker, worker)
        worker.finish()
        self.manager._debounce.stop()
        self.assertTrue(self.manager.settings['last_sync'])
        self.manager.sync_now(force=False)
        self.assertFalse(self.manager.busy)
        atomic_write(self.root / 'theme.json', encode({'LANGUAGE': 'en'}))
        self.manager.sync_now(force=False)
        self.assertTrue(self.manager.busy)

    def test_restore_list_delivered_only_when_next_operation_can_start(self):
        self.connect()
        seen = []
        self.manager.backups_ready.connect(lambda backups: seen.append(self.manager.busy))
        self.manager.list_backups()
        self.manager._worker.finish(backups=[{'id': 'test'}])
        self.assertEqual(seen, [False])

    def test_disabling_automatic_backup_stops_pending_save(self):
        self.connect()
        self.manager.schedule_sync()
        self.assertTrue(self.manager._debounce.isActive())
        self.manager.set_option('automatic', False)
        self.assertFalse(self.manager._debounce.isActive())

    def test_settings_show_drive_and_live_translation(self):
        theme = ThemeManager()
        theme.config_dir = self.root
        theme.config_path = self.root / 'theme.json'
        dialog = SettingsDialog(theme, sync_manager=self.manager)
        self.addCleanup(dialog.close)
        self.addCleanup(lambda: language_manager.set_language('pl', persist=False))
        language_manager.set_language('en', persist=False)
        self.assertEqual(dialog.cloud_settings.login_button.text(), 'Sign in with Google')
        self.assertFalse(dialog.cloud_settings.backup_button.isEnabled())
        self.connect()
        self.assertTrue(dialog.cloud_settings.backup_button.isEnabled())
        self.assertEqual(dialog.cloud_settings.account.text(), 'example@example.com')


@unittest.skipUnless(drive.HAS_GOOGLE_API, 'Google libraries required')
class GoogleProtocolTests(unittest.TestCase):
    def test_drive_upload_updates_only_this_devices_file(self):
        with patch.object(drive, 'AuthorizedSession'):
            client = drive.DriveClient(MagicMock(), MagicMock())
        client.list_backups = MagicMock(return_value=[{'id': 'other', 'name': 'music-crow-other.json'},
                                                       {'id': 'mine', 'name': 'music-crow-device.json'}])
        client.request = MagicMock()
        client.request.return_value.headers = {'Location': drive.UPLOAD_API + '?upload_id=test'}
        client.upload('device', b'{}')
        call = client.request.call_args_list[0]
        self.assertEqual(call.args[:2], ('PATCH', drive.UPLOAD_API + '/mine'))
        self.assertEqual(client.request.call_args.kwargs['data'], b'{}')

    def test_first_upload_is_in_application_data_folder(self):
        with patch.object(drive, 'AuthorizedSession'):
            client = drive.DriveClient(MagicMock(), MagicMock())
        client.list_backups = MagicMock(return_value=[])
        client.request = MagicMock()
        client.request.return_value.headers = {'Location': drive.UPLOAD_API + '?upload_id=test'}
        client.upload('device', b'{}')
        metadata = client.request.call_args_list[0].kwargs['json']
        self.assertEqual(metadata['parents'], ['appDataFolder'])
        self.assertEqual(drive.SCOPES, ['https://www.googleapis.com/auth/drive.appdata'])

    def test_remote_listing_paginates(self):
        with patch.object(drive, 'AuthorizedSession'):
            client = drive.DriveClient(MagicMock(), MagicMock())
        first = MagicMock(); first.json.return_value = {'nextPageToken': 'next', 'files': [{'id': '1', 'name': 'music-crow-1.json'}]}
        second = MagicMock(); second.json.return_value = {'files': [{'id': '2', 'name': 'music-crow-2.json'}]}
        client.request = MagicMock(side_effect=[first, second])
        self.assertEqual(len(client.list_backups()), 2)
        self.assertEqual(client.request.call_args.kwargs['params']['pageToken'], 'next')

    def test_download_rejects_an_id_outside_app_folder(self):
        with patch.object(drive, 'AuthorizedSession'):
            client = drive.DriveClient(MagicMock(), MagicMock())
        client.list_backups = MagicMock(return_value=[])
        client.request = MagicMock()
        with self.assertRaises(ValueError): client.download('arbitrary-file')
        client.request.assert_not_called()

    def test_loopback_oauth_uses_pkce_state_and_cancellation_checks(self):
        from urllib.parse import urlparse, parse_qs
        worker = MagicMock()
        urls = []
        worker.open_browser.emit.side_effect = urls.append
        class Server:
            server_port = 45678
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def handle_request(self):
                query = parse_qs(urlparse(urls[0]).query)
                start = MagicMock()
                application({'PATH_INFO': '/', 'QUERY_STRING': 'state=wrong&code=bad'}, start)
                self.status = start.call_args.args[0]
                application({'PATH_INFO': '/', 'QUERY_STRING': 'state=' + query['state'][0] + '&code=good'}, MagicMock())
        server = Server()
        def create_server(host, port, app, **kwargs):
            nonlocal application
            application = app
            self.assertEqual(host, '127.0.0.1')
            self.assertEqual(port, 0)
            return server
        application = None
        def fetch(flow, **kwargs):
            self.assertEqual(kwargs['code'], 'good')
            self.assertEqual(kwargs['timeout'], 20)
            flow.oauth2session.token = {'access_token': 'test-access', 'refresh_token': 'test-refresh', 'token_type': 'Bearer', 'expires_at': 9999999999}
        with patch.object(drive, 'make_server', side_effect=create_server), patch.object(drive.InstalledAppFlow, 'fetch_token', fetch):
            creds = drive.authorize(worker, CLIENT)
        params = parse_qs(urlparse(urls[0]).query)
        self.assertEqual(params['code_challenge_method'], ['S256'])
        self.assertTrue(params['code_challenge'])
        self.assertEqual(params['redirect_uri'], ['http://127.0.0.1:45678/'])
        self.assertEqual(server.status, '400 Bad Request')
        self.assertEqual(creds.refresh_token, 'test-refresh')
        worker.check_cancelled.assert_called()
