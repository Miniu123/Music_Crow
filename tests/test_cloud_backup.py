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
from core.cloud_backup import collect_snapshot, restore_snapshot, validate_snapshot, encode, atomic_write, TRACK_FIELDS
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

    def test_null_metadata_in_playlists_and_history_can_be_backed_up_and_restored(self):
        track = {field: None for field in TRACK_FIELDS}
        track.update(url=TRACK['url'], duration=None)
        self.write('playlists/Favourites.json', {'tracks': [track, TRACK]})
        self.write('listening_history.json', {'track': {'track': track, 'plays': 3, 'last_played': 123.0}})
        original = (self.root / 'playlists/Favourites.json').read_bytes()
        for include_history in (False, True):
            with self.subTest(include_history=include_history):
                snapshot = collect_snapshot(self.root, include_history=include_history)
                cleaned = snapshot['playlists']['Favourites']['tracks'][0]
                self.assertEqual(cleaned['url'], TRACK['url'])
                self.assertEqual(cleaned['duration'], 0)
                for field in TRACK_FIELDS:
                    if field != 'url':
                        self.assertEqual(cleaned[field], '')
                self.assertEqual(len(snapshot['playlists']['Favourites']['tracks']), 2)
                if include_history:
                    self.assertEqual(snapshot['history']['track']['track'], cleaned)
                destination = self.root / ('restored-' + str(include_history))
                restore_snapshot(destination, snapshot)
                restored = collect_snapshot(destination, include_history=include_history)
                self.assertEqual(restored['playlists'], snapshot['playlists'])
                self.assertEqual(restored['history'], snapshot['history'])
        self.assertEqual((self.root / 'playlists/Favourites.json').read_bytes(), original)

    def test_non_text_metadata_other_than_null_is_still_rejected(self):
        for value in (42, False, [], {}, 'x' * 20001):
            with self.subTest(value_type=type(value).__name__):
                self.write('playlists/Favourites.json', {'tracks': [dict(TRACK, title=value)]})
                with self.assertRaises(ValueError):
                    collect_snapshot(self.root)

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
        if self.operation == 'upload':
            values.setdefault('remote', {'id': 'account-config', 'checksum': 'uploaded-checksum'})
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

    def test_manual_backup_with_missing_metadata_reaches_upload_worker(self):
        self.connect()
        atomic_write(self.root / 'playlists/Test.json', encode({
            'tracks': [dict(TRACK, title=None, uploader=None, duration=None)]}))
        self.manager.sync_now()
        self.assertTrue(self.manager.busy)
        self.assertEqual(self.manager._worker.operation, 'upload')
        payload = json.loads(self.manager._worker.kwargs['payload'])
        self.assertEqual(payload['playlists']['Test']['tracks'][0]['url'], TRACK['url'])
        self.manager._worker.finish()
        self.assertEqual(self.manager.status, 'Kopia została zapisana na Dysku Google.')

    def test_bundled_desktop_client_logs_in_without_a_user_config_file(self):
        from ui.cloud_settings import CloudSettings
        with patch.object(drive, 'bundled_client', return_value=CLIENT):
            controls = CloudSettings(self.manager)
            self.addCleanup(controls.close)
            self.assertTrue(self.manager.has_client_configuration())
            self.assertTrue(controls.login_button.isEnabled())
            self.assertTrue(controls.configure_button.isHidden())
            self.assertTrue(controls.advanced_button.isHidden())
            controls.login_button.click()
            self.assertEqual(self.manager._worker.kwargs['client'], CLIENT)
            self.assertFalse(self.manager.client_path.exists())
            urls = []
            self.manager.open_browser.connect(urls.append)
            self.manager._worker.open_browser.emit('https://accounts.google.com/o/oauth2/auth')
            self.assertEqual(urls, ['https://accounts.google.com/o/oauth2/auth'])

    def test_missing_release_configuration_does_not_start_authentication(self):
        from ui.cloud_settings import CloudSettings
        with patch.object(drive, 'bundled_client', return_value=None):
            self.manager.login()
            self.assertFalse(self.manager.busy)
            self.assertEqual(self.manager.status, 'Autor aplikacji musi najpierw skonfigurować logowanie Google.')
            controls = CloudSettings(self.manager)
            self.addCleanup(controls.close)
            self.assertFalse(controls.login_button.isEnabled())
            self.assertTrue(controls.configure_button.isHidden())

    def test_local_client_keeps_precedence_and_can_be_repaired(self):
        from ui.cloud_settings import CloudSettings
        other = copy.deepcopy(CLIENT)
        other['installed']['client_id'] = 'publisher.apps.googleusercontent.com'
        atomic_write(self.manager.client_path, encode(CLIENT))
        with patch.object(drive, 'bundled_client', return_value=other):
            self.assertEqual(self.manager._client_configuration(), CLIENT)
            self.manager.client_path.write_text('invalid JSON')
            self.assertFalse(self.manager.has_client_configuration())
            controls = CloudSettings(self.manager)
            self.addCleanup(controls.close)
            self.assertFalse(controls.advanced_button.isHidden())
            controls.advanced_button.click()
            self.assertFalse(controls.configure_button.isHidden())

    def test_bundled_client_must_pass_same_endpoint_validation(self):
        bad = copy.deepcopy(CLIENT)
        bad['installed']['token_uri'] = 'https://untrusted.example/token'
        with patch.object(drive, 'bundled_client', return_value=bad):
            self.manager.login()
            self.assertFalse(self.manager.has_bundled_credentials())
            self.assertFalse(self.manager.busy)
            self.assertEqual(self.manager.status, 'Konfiguracja logowania Google jest nieprawidłowa.')

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

    def test_uploaded_file_checkpoint_is_reused_after_restart(self):
        self.connect()
        self.manager.sync_now()
        self.manager._worker.finish(remote={'id': 'one-file', 'checksum': 'first-content'})
        state = json.loads(self.manager.state_path.read_text())
        self.assertEqual(state['remote_file_id'], 'one-file')
        self.assertEqual(state['remote_checksum'], 'first-content')
        self.manager.shutdown()
        resumed = drive.GDriveSyncManager(root=self.root)
        self.addCleanup(resumed.shutdown)
        self.assertEqual(resumed.settings['remote_file_id'], 'one-file')
        resumed.connected = True
        resumed.sync_now()
        self.assertEqual(resumed._worker.kwargs['expected_file_id'], 'one-file')
        self.assertEqual(resumed._worker.kwargs['expected_checksum'], 'first-content')
        self.assertNotIn('device_id', resumed._worker.kwargs)

    def test_account_switch_resets_remote_checkpoint(self):
        self.connect()
        self.manager.settings.update(remote_file_id='account-A-file', remote_checksum='A-content')
        self.manager._start('connect')
        self.manager._worker.finish(email='other@example.com')
        self.manager._debounce.stop()
        self.assertEqual(self.manager.settings['account_email'], 'other@example.com')
        self.assertEqual(self.manager.settings['remote_file_id'], '')
        self.assertEqual(self.manager.settings['remote_checksum'], '')

    def test_conflict_blocks_automatic_and_manual_writes_until_restore(self):
        self.connect()
        self.manager._fail(drive.REMOTE_CONFLICT)
        self.manager.schedule_sync()
        self.assertFalse(self.manager._debounce.isActive())
        self.manager.sync_now(force=True)
        self.assertFalse(self.manager.busy)
        self.manager.restore_ready.connect(self.manager.apply_restore)
        self.manager.download_backup('cloud-config')
        snapshot = collect_snapshot(self.root)
        snapshot['settings']['LANGUAGE'] = 'en'
        self.manager._worker.finish(snapshot=snapshot, remote={'id': 'cloud-config', 'checksum': 'restored-content'})
        self.assertFalse(self.manager.needs_restore)
        self.assertEqual(self.manager.settings['remote_file_id'], 'cloud-config')
        self.assertEqual(self.manager.settings['remote_checksum'], 'restored-content')
        self.assertEqual(json.loads((self.root / 'theme.json').read_text())['LANGUAGE'], 'en')
        self.manager._debounce.stop()
        self.manager.sync_now()
        self.assertEqual(self.manager._worker.kwargs['expected_checksum'], 'restored-content')

    def test_cancelled_restore_never_acknowledges_remote_file(self):
        self.connect()
        self.manager.download_backup('cloud-config')
        self.manager._worker.finish(snapshot=collect_snapshot(self.root),
                                    remote={'id': 'cloud-config', 'checksum': 'not-applied'})
        self.assertTrue(self.manager.needs_restore)
        self.assertEqual(self.manager.settings['remote_file_id'], '')
        self.manager.sync_now()
        self.assertFalse(self.manager.busy)

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
    def test_unknown_or_changed_cloud_copy_is_not_overwritten(self):
        for file_id, checksum in (('', ''), ('config', 'old'), ('another-account-file', 'current')):
            with self.subTest(file_id=file_id, checksum=checksum), patch.object(drive, 'AuthorizedSession'):
                client = drive.DriveClient(MagicMock(), MagicMock())
                client.list_backups = MagicMock(return_value=[{'id': 'config', 'name': drive.CONFIG_NAME, 'md5Checksum': 'current'}])
                client.request = MagicMock()
                with self.assertRaisesRegex(ValueError, drive.REMOTE_CONFLICT):
                    client.upload(b'{}', file_id, checksum)
                client.request.assert_not_called()

    def test_accounts_use_their_own_credentials_and_file_ids(self):
        credentials = [MagicMock(), MagicMock()]
        sessions = [MagicMock(), MagicMock()]
        with patch.object(drive, 'AuthorizedSession', side_effect=sessions) as factory:
            clients = [drive.DriveClient(credential, MagicMock()) for credential in credentials]
        self.assertEqual([call.args[0] for call in factory.call_args_list], credentials)
        for index, client in enumerate(clients):
            file_id = f'account-{index}-config'
            response = sessions[index].request.return_value
            response.headers = {'Location': drive.UPLOAD_API + '?upload_id=test'}
            response.json.return_value = {'id': file_id}
            client.list_backups = MagicMock(return_value=[{'id': file_id, 'name': drive.CONFIG_NAME, 'md5Checksum': 'known'}])
            client.upload(b'{}', file_id, 'known')
            self.assertEqual(sessions[index].request.call_args_list[0].args[:2], ('PATCH', drive.UPLOAD_API + '/' + file_id))

    def test_download_checkpoint_describes_received_bytes(self):
        import hashlib
        payload = encode({'format': 'music-crow-backup', 'version': 1, 'settings': {}, 'playlists': {}, 'history': {}})
        with patch.object(drive, 'AuthorizedSession'):
            client = drive.DriveClient(MagicMock(), MagicMock())
        client.list_backups = MagicMock(return_value=[{'id': 'config', 'name': drive.CONFIG_NAME, 'size': str(len(payload)), 'md5Checksum': 'before-download'}])
        client.request = MagicMock()
        client.request.return_value.iter_content.return_value = [payload]
        result = client.download('config')
        self.assertEqual(result['remote'], {'id': 'config', 'checksum': hashlib.md5(payload, usedforsecurity=False).hexdigest()})
        self.assertEqual(result['snapshot']['format'], 'music-crow-backup')
        client.request.return_value.close.assert_called_once()

    def test_drive_upload_updates_account_config_and_preserves_legacy_files(self):
        with patch.object(drive, 'AuthorizedSession'):
            client = drive.DriveClient(MagicMock(), MagicMock())
        client.list_backups = MagicMock(return_value=[{'id': 'other', 'name': 'music-crow-other.json'},
                                                       {'id': 'mine', 'name': drive.CONFIG_NAME, 'md5Checksum': 'known'}])
        client.request = MagicMock()
        client.request.return_value.headers = {'Location': drive.UPLOAD_API + '?upload_id=test'}
        client.request.return_value.json.return_value = {'id': 'mine'}
        client.upload(b'{}', 'mine', 'known')
        call = client.request.call_args_list[0]
        self.assertEqual(call.args[:2], ('PATCH', drive.UPLOAD_API + '/mine'))
        self.assertEqual(client.request.call_args.kwargs['data'], b'{}')

    def test_first_upload_is_in_application_data_folder(self):
        with patch.object(drive, 'AuthorizedSession'):
            client = drive.DriveClient(MagicMock(), MagicMock())
        client.list_backups = MagicMock(return_value=[])
        client.request = MagicMock()
        client.request.return_value.headers = {'Location': drive.UPLOAD_API + '?upload_id=test'}
        client.request.return_value.json.return_value = {'id': 'new'}
        client.upload(b'{}')
        metadata = client.request.call_args_list[0].kwargs['json']
        self.assertEqual(metadata['parents'], ['appDataFolder'])
        self.assertEqual(metadata['name'], drive.CONFIG_NAME)
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
