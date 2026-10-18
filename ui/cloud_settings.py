"""Google Drive controls used by the settings dialog."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QFileDialog, QInputDialog
from core.i18n import tr, text, set_text, language_manager


class CloudSettings(QWidget):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        description = text(QLabel(), 'Zapisuj ustawienia, playlisty i okładki na swoim Dysku Google. Każde urządzenie ma osobną kopię.')
        description.setWordWrap(True)
        description.setObjectName('SettingsRowDescription')
        layout.addWidget(description)
        self.account = QLabel()
        self.account.setObjectName('SettingsRowTitle')
        self.account.setWordWrap(True)
        layout.addWidget(self.account)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setObjectName('SettingsRowDescription')
        layout.addWidget(self.status)
        self.last_backup = QLabel()
        self.last_backup.setObjectName('SettingsRowDescription')
        layout.addWidget(self.last_backup)
        self.configure_button = text(QPushButton(), 'Wybierz konfigurację Google…')
        self.configure_button.clicked.connect(self._configure)
        layout.addWidget(self.configure_button)
        hint = text(QLabel(), 'Pierwsze uruchomienie wymaga pliku OAuth aplikacji komputerowej. Instrukcja: README → Dysk Google.')
        hint.setWordWrap(True)
        hint.setObjectName('SettingsRowDescription')
        layout.addWidget(hint)
        self.automatic = text(QCheckBox(), 'Automatycznie zapisuj kopię')
        self.history = text(QCheckBox(), 'Uwzględniaj historię słuchania')
        layout.addWidget(self.automatic)
        layout.addWidget(self.history)
        self.automatic.toggled.connect(lambda value: manager.set_option('automatic', value))
        self.history.toggled.connect(lambda value: manager.set_option('include_history', value))
        row = QHBoxLayout()
        self.login_button = text(QPushButton(), 'Zaloguj przez Google')
        self.login_button.setObjectName('PrimaryButton')
        self.login_button.clicked.connect(manager.login)
        self.logout_button = text(QPushButton(), 'Wyloguj')
        self.logout_button.clicked.connect(manager.logout)
        self.cancel_button = text(QPushButton(), 'Anuluj')
        self.cancel_button.clicked.connect(manager.cancel)
        for button in (self.login_button, self.logout_button, self.cancel_button):
            row.addWidget(button)
        layout.addLayout(row)
        actions = QHBoxLayout()
        self.backup_button = text(QPushButton(), 'Zapisz kopię teraz')
        self.backup_button.clicked.connect(lambda: manager.sync_now(force=True))
        self.restore_button = text(QPushButton(), 'Przywróć kopię…')
        self.restore_button.clicked.connect(manager.list_backups)
        actions.addWidget(self.backup_button)
        actions.addWidget(self.restore_button)
        layout.addLayout(actions)
        manager.state_changed.connect(self.refresh)
        language_manager.changed.connect(self.refresh)
        manager.backups_ready.connect(self._choose_backup)
        self.refresh()

    def refresh(self):
        manager = self.manager
        busy, connected = manager.busy, manager.connected
        self.account.setText(manager.email)
        set_text(self.status, manager.status)
        stamp = manager.settings['last_sync']
        if stamp:
            from datetime import datetime
            try:
                stamp = datetime.fromisoformat(stamp).astimezone().strftime('%Y-%m-%d %H:%M')
            except ValueError:
                stamp = ''
        set_text(self.last_backup, 'Ostatnia kopia:')
        if stamp:
            self.last_backup.setText(tr('Ostatnia kopia:') + ' ' + stamp)
        self.last_backup.setVisible(bool(stamp))
        self.configure_button.setEnabled(not busy and not connected)
        self.login_button.setVisible(not connected)
        self.login_button.setEnabled(not busy and manager.is_available())
        self.logout_button.setVisible(connected)
        self.cancel_button.setVisible(busy)
        self.backup_button.setEnabled(connected and not busy)
        self.restore_button.setEnabled(connected and not busy)
        for checkbox, key in ((self.automatic, 'automatic'), (self.history, 'include_history')):
            checkbox.blockSignals(True)
            checkbox.setChecked(manager.settings[key])
            checkbox.blockSignals(False)
        if not manager.is_available():
            set_text(self.status, 'Brakuje bibliotek Google. Zainstaluj zależności projektu.')

    def _configure(self):
        path, _ = QFileDialog.getOpenFileName(self, tr('Wybierz konfigurację Google…'), '', 'JSON (*.json)')
        if path:
            self.manager.configure(path)

    def _choose_backup(self, backups):
        if not backups or not self.isVisible():
            return
        labels = [f"{entry.get('modifiedTime', '')[:19].replace('T', ' ')} UTC · {entry['name'][11:-5]}" for entry in backups]
        chosen, ok = QInputDialog.getItem(self, tr('Przywróć kopię…'), tr('Wybierz kopię do przywrócenia.'), labels, 0, False)
        if ok:
            self.manager.download_backup(backups[labels.index(chosen)]['id'])
