"""Shared playlist picker for search, recommendations and the player bar."""
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QMenu, QDialog, QMessageBox, QToolTip
from core.i18n import tr
from core.recommendations import track_key
from ui.create_playlist_dialog import CreatePlaylistDialog


def save_track(manager, name, track, parent=None):
    try:
        # Recommendation ranking fields belong to the session, not the library.
        clean = {key: value for key, value in track.items()
                 if not key.startswith('_') and not key.startswith('recommendation_')}
        manager.add_track(name, clean)
        QToolTip.showText(QCursor.pos(), tr('Zapisano na playliście'), parent)
        return True
    except (OSError, ValueError, TypeError):
        QMessageBox.warning(parent, tr('Dodaj do playlisty'), tr('Nie udało się zapisać utworu.'))
        return False


def create_and_save(parent, manager, track):
    dialog = CreatePlaylistDialog(parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    name = dialog.name_input.text().strip()
    if not name:
        QMessageBox.information(parent, tr('Dodaj do playlisty'), tr('Podaj nazwę playlisty.'))
        return
    try:
        if not manager.create_playlist(name):
            QMessageBox.information(parent, tr('Dodaj do playlisty'), tr('Playlista o tej nazwie już istnieje.'))
            return
        if dialog.image_path:
            manager.set_cover_image(name, dialog.image_path)
        save_track(manager, name, track, parent)
    except (OSError, ValueError, TypeError):
        QMessageBox.warning(parent, tr('Dodaj do playlisty'), tr('Nie udało się zapisać utworu.'))


def build_playlist_menu(parent, manager, track, player=None):
    menu = QMenu(parent)
    if player:
        menu.addAction(tr('Odtwórz jako następny'), lambda: player.add_to_queue(track, play_next=True))
        menu.addAction(tr('Dodaj do kolejki'), lambda: player.add_to_queue(track))
        menu.addSeparator()
    if manager:
        for name in manager.list_playlists():
            action = menu.addAction(name)
            action.setData(name)
            try:
                saved = any(track_key(item) == track_key(track) for item in manager.get_tracks(name))
            except (OSError, ValueError, TypeError):
                action.setEnabled(False)
                continue
            if saved:
                action.setCheckable(True)
                action.setChecked(True)
                action.setEnabled(False)
            else:
                action.triggered.connect(lambda checked=False, n=name: save_track(manager, n, track, parent))
        if manager.list_playlists():
            menu.addSeparator()
        create = menu.addAction(tr('Utwórz nową playlistę…'))
        create.setData('__create__')
        create.triggered.connect(lambda: create_and_save(parent, manager, track))
    return menu


def show_playlist_menu(parent, manager, track, player=None):
    menu = build_playlist_menu(parent, manager, track, player)
    menu.exec(QCursor.pos())
    menu.deleteLater()
