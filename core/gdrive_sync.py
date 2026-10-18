"""Google OAuth desktop login and per-device Google Drive app-data backups."""
import hashlib
import json
import secrets
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from wsgiref.simple_server import make_server, WSGIRequestHandler
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from core.cloud_backup import atomic_write, collect_snapshot, encode, validate_snapshot, MAX_BACKUP_BYTES

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import AuthorizedSession
    from google_auth_oauthlib.flow import InstalledAppFlow
    HAS_GOOGLE_API = True
except ImportError:
    HAS_GOOGLE_API = False

SCOPES = ['https://www.googleapis.com/auth/drive.appdata']
API = 'https://www.googleapis.com/drive/v3'
UPLOAD_API = 'https://www.googleapis.com/upload/drive/v3/files'


def validate_client(data):
    client = data.get('installed') if isinstance(data, dict) else None
    if (not isinstance(client, dict) or not isinstance(client.get('client_id'), str)
            or not client['client_id'].endswith('.apps.googleusercontent.com')
            or not isinstance(client.get('client_secret'), str) or not client['client_secret']
            or client.get('auth_uri') != 'https://accounts.google.com/o/oauth2/auth'
            or client.get('token_uri') != 'https://oauth2.googleapis.com/token'):
        raise ValueError('Wybierz plik OAuth typu Aplikacja komputerowa z Google Cloud.')
    return {'installed': client}


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass  # Callback URLs contain authorization codes; never log them.


def authorize(worker, client):
    flow = InstalledAppFlow.from_client_config(client, SCOPES, autogenerate_code_verifier=True)
    callback = {}
    expected_state = ''

    def application(environ, start_response):
        values = parse_qs(environ.get('QUERY_STRING', ''))
        state = values.get('state', [''])[0]
        valid = bool(state and secrets.compare_digest(state, expected_state))
        if valid and environ.get('PATH_INFO') == '/' and ('code' in values or 'error' in values):
            callback.update(values)
            start_response('200 OK', [('Content-Type', 'text/plain; charset=utf-8')])
            return [b'Music Crow: You can return to the app. / Mozesz wrocic do aplikacji.']
        start_response('400 Bad Request', [('Content-Type', 'text/plain')])
        return [b'Invalid authorization response.']

    with make_server('127.0.0.1', 0, application, handler_class=QuietHandler) as server:
        server.timeout = 0.25
        flow.redirect_uri = f'http://127.0.0.1:{server.server_port}/'
        url, expected_state = flow.authorization_url(prompt='consent', access_type='offline')
        worker.open_browser.emit(url)
        deadline = time.monotonic() + 180
        while not callback:
            worker.check_cancelled()
            if time.monotonic() >= deadline:
                raise ValueError('Logowanie anulowane lub przekroczono czas oczekiwania.')
            server.handle_request()
        worker.check_cancelled()
        if 'error' in callback:
            raise ValueError('Logowanie anulowane lub przekroczono czas oczekiwania.')
        flow.fetch_token(code=callback['code'][0], timeout=20)
        return flow.credentials


class DriveClient:
    def __init__(self, credentials, worker):
        self.credentials = credentials
        self.worker = worker
        self.session = AuthorizedSession(credentials, refresh_timeout=20)

    def request(self, method, url, **kwargs):
        self.worker.check_cancelled()
        response = self.session.request(method, url, timeout=(5, 20), **kwargs)
        response.raise_for_status()
        self.worker.check_cancelled()
        return response

    def account(self):
        data = self.request('GET', API + '/about', params={'fields': 'user(emailAddress)'}).json()
        return data.get('user', {}).get('emailAddress', '')

    def list_backups(self):
        entries, token = [], None
        for _ in range(20):
            params = {'spaces': 'appDataFolder', 'q': 'trashed=false', 'pageSize': 100,
                      'fields': 'nextPageToken,files(id,name,modifiedTime,size)', 'orderBy': 'modifiedTime desc'}
            if token:
                params['pageToken'] = token
            data = self.request('GET', API + '/files', params=params).json()
            entries.extend(item for item in data.get('files', [])
                           if item.get('name', '').startswith('music-crow-') and item['name'].endswith('.json'))
            token = data.get('nextPageToken')
            if not token:
                return entries
        raise ValueError('Zbyt wiele kopii na Dysku Google.')

    def upload(self, device_id, payload):
        name = f'music-crow-{device_id}.json'
        matches = [item for item in self.list_backups() if item['name'] == name]
        headers = {'X-Upload-Content-Type': 'application/json', 'X-Upload-Content-Length': str(len(payload))}
        if matches:
            response = self.request('PATCH', UPLOAD_API + '/' + matches[0]['id'],
                                    params={'uploadType': 'resumable'}, json={}, headers=headers)
        else:
            metadata = {'name': name, 'parents': ['appDataFolder'], 'mimeType': 'application/json'}
            response = self.request('POST', UPLOAD_API, params={'uploadType': 'resumable', 'fields': 'id'},
                                    json=metadata, headers=headers)
        target = response.headers.get('Location', '')
        parsed = urlparse(target)
        if parsed.scheme != 'https' or parsed.hostname != 'www.googleapis.com' or parsed.username:
            raise ValueError('Invalid Google upload session')
        # A resumable session also supports backups larger than the 5 MB multipart recommendation.
        return self.request('PUT', target, data=payload, headers={'Content-Type': 'application/json'}).json()

    def download(self, file_id):
        # Only accept IDs returned from this application's private folder.
        selected = next((item for item in self.list_backups() if item['id'] == file_id), None)
        if selected is None or int(selected.get('size', 0)) > MAX_BACKUP_BYTES:
            raise ValueError('Nieprawidłowa kopia danych.')
        response = self.request('GET', API + '/files/' + file_id, params={'alt': 'media'}, stream=True)
        payload = bytearray()
        try:
            for chunk in response.iter_content(64 * 1024):
                self.worker.check_cancelled()
                payload.extend(chunk)
                if len(payload) > MAX_BACKUP_BYTES:
                    raise ValueError('Kopia przekracza limit 40 MB.')
        finally:
            response.close()
        return validate_snapshot(json.loads(payload))


class DriveWorker(QThread):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    open_browser = pyqtSignal(str)

    def __init__(self, operation, token=None, client=None, payload=None, device_id='', file_id='', parent=None):
        super().__init__(parent)
        self.operation, self.token, self.client = operation, token, client
        self.payload, self.device_id, self.file_id = payload, device_id, file_id

    def check_cancelled(self):
        if self.isInterruptionRequested():
            raise InterruptedError()

    def run(self):
        drive = None
        try:
            self.check_cancelled()
            creds = authorize(self, self.client) if self.operation == 'login' else Credentials.from_authorized_user_info(self.token, SCOPES)
            drive = DriveClient(creds, self)
            result = {'operation': self.operation}
            if self.operation in ('login', 'connect'):
                result['email'] = drive.account()
            elif self.operation == 'upload':
                drive.upload(self.device_id, self.payload)
            elif self.operation == 'list':
                result['backups'] = drive.list_backups()
            elif self.operation == 'download':
                result['snapshot'] = drive.download(self.file_id)
            self.check_cancelled()
            result['token'] = json.loads(creds.to_json())
            self.completed.emit(result)
        except InterruptedError:
            pass
        except Exception as error:
            # Avoid displaying token-bearing URLs or OAuth responses in the UI/logs.
            if isinstance(error, ValueError) and str(error) in (
                'Logowanie anulowane lub przekroczono czas oczekiwania.',
                'Nieprawidłowa kopia danych.', 'Kopia przekracza limit 40 MB.', 'Zbyt wiele kopii na Dysku Google.'):
                message = str(error)
            elif getattr(getattr(error, 'response', None), 'status_code', None) == 403:
                message = 'Brak dostępu do Dysku. Sprawdź, czy Drive API jest włączone w projekcie Google.'
            else:
                message = 'Operacja Google nie powiodła się. Sprawdź połączenie lub zaloguj się ponownie.'
            self.failed.emit(message)
        finally:
            if drive:
                drive.session.close()


class GDriveSyncManager(QObject):
    state_changed = pyqtSignal()
    login_status_changed = pyqtSignal(bool)
    sync_finished = pyqtSignal(int)
    backups_ready = pyqtSignal(list)
    restore_ready = pyqtSignal(dict)
    open_browser = pyqtSignal(str)
    data_restored = pyqtSignal()

    def __init__(self, parent=None, root=None):
        super().__init__(parent)
        self.root = Path(root) if root else Path.home() / '.config/music-crow'
        self.root.mkdir(parents=True, exist_ok=True)
        self.token_path = self.root / 'google_token.json'
        self.client_path = self.root / 'credentials.json'
        self.state_path = self.root / 'cloud_state.json'
        self._token = None
        self._worker = None
        self._generation = 0
        self._pending = False
        self._closing = False
        self.connected = False
        self.email = ''
        self.status = 'Dysk Google nie jest połączony.'
        self.settings = {'device_id': uuid.uuid4().hex, 'automatic': True, 'include_history': False,
                         'last_sync': '', 'digest': ''}
        try:
            state = json.loads(self.state_path.read_text())
            if isinstance(state, dict):
                for key in self.settings:
                    if key in state and type(state[key]) is type(self.settings[key]):
                        self.settings[key] = state[key]
        except (OSError, ValueError):
            pass
        self._auto = QTimer(self)
        self._auto.setInterval(5 * 60 * 1000)
        self._auto.timeout.connect(self.schedule_sync)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(3000)
        self._debounce.timeout.connect(lambda: self.sync_now(force=False))
        QTimer.singleShot(0, self._resume)

    @property
    def busy(self):
        return self._worker is not None

    def is_available(self):
        return HAS_GOOGLE_API

    def has_credentials_file(self):
        return self.client_path.is_file()

    def is_logged_in(self):
        return self.connected

    def _save_state(self):
        atomic_write(self.state_path, encode(self.settings))

    def configure(self, path):
        if self.busy or self.connected:
            return
        try:
            client = validate_client(json.loads(Path(path).read_text()))
            atomic_write(self.client_path, encode(client))
            self.status = 'Konfiguracja Google gotowa. Możesz się zalogować.'
        except (OSError, ValueError):
            self.status = 'Wybierz plik OAuth typu Aplikacja komputerowa z Google Cloud.'
        self.state_changed.emit()

    def _resume(self):
        if self._closing or self.busy or not HAS_GOOGLE_API or not self.token_path.exists():
            return
        try:
            self._token = json.loads(self.token_path.read_text())
            if not isinstance(self._token, dict) or not set(SCOPES).issubset(self._token.get('scopes', [])):
                self._token = None
                return
        except (OSError, ValueError, TypeError):
            return
        self._start('connect')

    def login(self):
        if self.busy or self._closing:
            return
        if not HAS_GOOGLE_API:
            self.status = 'Brakuje bibliotek Google. Zainstaluj zależności projektu.'
        elif not self.has_credentials_file():
            self.status = 'Najpierw wybierz plik konfiguracji Google.'
        else:
            try:
                client = validate_client(json.loads(self.client_path.read_text()))
                self._start('login', client=client)
                return
            except (OSError, ValueError):
                self.status = 'Wybierz plik OAuth typu Aplikacja komputerowa z Google Cloud.'
        self.state_changed.emit()

    def logout(self):
        self._generation += 1
        if self._worker:
            self._worker.requestInterruption()
        self._auto.stop()
        self._debounce.stop()
        self._pending = False
        self._delivery = None
        self._token = None
        self.connected = False
        self.email = ''
        self.settings.update(digest='', last_sync='')
        try:
            self.token_path.unlink(missing_ok=True)
            self._save_state()
            self.status = 'Dysk Google nie jest połączony.'
        except OSError:
            self.status = 'Nie udało się usunąć lokalnej sesji Google.'
        self.login_status_changed.emit(False)
        self.state_changed.emit()

    def cancel(self):
        self._delivery = None
        self._generation += 1
        self._pending = False
        if self._worker:
            self._worker.requestInterruption()
        self.status = 'Operacja anulowana.'
        self.state_changed.emit()

    def set_option(self, key, value):
        if key not in ('automatic', 'include_history'):
            return
        self.settings[key] = bool(value)
        try:
            self._save_state()
        except OSError:
            self.status = 'Nie udało się zapisać lokalnych danych Google.'
        if not self.settings['automatic']:
            self._pending = False
            self._debounce.stop()
        elif self.connected:
            self.schedule_sync()
        self.state_changed.emit()

    def schedule_sync(self, *args):
        if self.connected and self.settings['automatic'] and not self._closing:
            self._debounce.start()

    def sync_now(self, force=True):
        if not self.connected or self._closing:
            return
        if self.busy:
            self._pending = True
            return
        try:
            snapshot = collect_snapshot(self.root, self.settings['include_history'])
            digest_data = dict(snapshot, created_at='')
            digest = hashlib.sha256(encode(digest_data)).hexdigest()
            if not force and digest == self.settings['digest']:
                return
            self._save_state()
            self._upload_digest = digest
            self._start('upload', payload=encode(snapshot), device_id=self.settings['device_id'])
        except (OSError, ValueError, TypeError):
            self.status = 'Nie udało się przygotować kopii. Sprawdź lokalne pliki i rozmiar okładek.'
            self.state_changed.emit()

    def list_backups(self):
        if self.connected and not self.busy:
            self._start('list')

    def download_backup(self, file_id):
        if self.connected and not self.busy:
            self._start('download', file_id=file_id)

    def _start(self, operation, **kwargs):
        self.status = {'login': 'Dokończ logowanie w przeglądarce…', 'connect': 'Łączę z Dyskiem Google…',
                       'upload': 'Zapisuję kopię na Dysku Google…', 'list': 'Pobieram listę kopii…',
                       'download': 'Pobieram kopię danych…'}[operation]
        worker = DriveWorker(operation, token=self._token, parent=self, **kwargs)
        self._worker = worker
        generation = self._generation
        worker.open_browser.connect(lambda url: self.open_browser.emit(url) if generation == self._generation and not self._closing else None)
        worker.completed.connect(lambda result: self._complete(result) if generation == self._generation and not self._closing else None)
        worker.failed.connect(lambda message: self._fail(message) if generation == self._generation and not self._closing else None)
        worker.finished.connect(lambda: self._finished(worker))
        worker.finished.connect(worker.deleteLater)
        self.state_changed.emit()
        worker.start()

    def _fail(self, message):
        self.status = message
        self.state_changed.emit()

    def _complete(self, result):
        try:
            self._token = result['token']
            atomic_write(self.token_path, encode(self._token))  # mkstemp gives owner-only permissions.
            operation = result['operation']
            if operation in ('login', 'connect'):
                if operation == 'login':
                    self.settings.update(digest='', last_sync='')
                    self._save_state()
                self.connected = True
                self.email = result['email']
                self.status = 'Połączono z Dyskiem Google.'
                self.login_status_changed.emit(True)
                self._auto.start()
                self.schedule_sync()
            elif operation == 'upload':
                self.settings.update(digest=self._upload_digest, last_sync=datetime.now(timezone.utc).isoformat())
                self._save_state()
                self.status = 'Kopia została zapisana na Dysku Google.'
                self.sync_finished.emit(1)
            elif operation == 'list':
                self.status = 'Wybierz kopię do przywrócenia.' if result['backups'] else 'Brak kopii na tym koncie Google.'
                # Deliver only after QThread.finished releases the busy state.
                self._delivery = ('list', result['backups'])
            elif operation == 'download':
                self.status = 'Kopia gotowa do przywrócenia.'
                self._delivery = ('download', result['snapshot'])
        except (OSError, ValueError):
            self.status = 'Nie udało się zapisać lokalnych danych Google.'
        self.state_changed.emit()

    def _finished(self, worker):
        if self._worker is worker:
            self._worker = None
        self.state_changed.emit()
        delivery = getattr(self, '_delivery', None)
        self._delivery = None
        if delivery and not self._closing:
            (self.backups_ready if delivery[0] == 'list' else self.restore_ready).emit(delivery[1])
        if self._pending and not self._closing:
            self._pending = False
            self.schedule_sync()

    def apply_restore(self, snapshot):
        from core.cloud_backup import restore_snapshot
        if self.busy:
            return
        try:
            restore_snapshot(self.root, snapshot)
            self.status = 'Przywrócono dane. Poprzedni stan zapisano w folderze recovery.'
            self.data_restored.emit()
            self.schedule_sync()
        except (OSError, ValueError, TypeError):
            self.status = 'Przywracanie nie powiodło się. Sprawdź kopię danych i dostęp do plików.'
        self.state_changed.emit()

    def shutdown(self):
        self._closing = True
        self._generation += 1
        self._auto.stop()
        self._debounce.stop()
        if self._worker:
            self._worker.requestInterruption()
            self._worker.wait()
