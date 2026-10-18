import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import unittest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import QMimeData, QPoint, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from core.player import MusicPlayer
from core.recommendations import PlaybackRecommendationManager, build_profile, track_key
from ui.queue_page import QueuePage, QueueTrackCard, DropContainer, QUEUE_MIME

app = QApplication.instance() or QApplication([])


def song(title, artist='Artist'):
    return {'url': 'https://example.com/' + title, 'title': title, 'uploader': artist}


class QueueTests(unittest.TestCase):
    def setUp(self):
        patcher = patch('core.player.mpv.MPV', side_effect=[MagicMock(), MagicMock()])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.player = MusicPlayer()
        self.addCleanup(self.player.shutdown)

    def test_priority_playlist_then_recommendations(self):
        p = self.player
        p.play_queue([song('A'), song('B'), song('C')])
        p.add_to_queue(song('Priority'))
        p.set_recommended_queue([song('R')])
        for title in ('Priority', 'B', 'C', 'R'):
            self.assertEqual(p._get_next_track_info()[0]['title'], title)
            p.next_track()
            self.assertEqual(p._current_track['title'], title)
        self.assertEqual(p._get_next_track_info(), (None, ''))

    def test_next_button_moves_suggestion_without_interrupting_current_track(self):
        p = self.player
        p.play_queue([song('A'), song('B')])
        p.add_to_queue(song('Already queued'))
        p.set_recommended_queue([song('R')])
        page = QueuePage(p)
        page.refresh()
        card = next(card for card in page._cards if card.queue_type == 'recommended')
        QTest.mouseClick(card.btn_play_next, Qt.MouseButton.LeftButton)
        self.assertEqual(p._current_track['title'], 'A')
        self.assertEqual(p._get_next_track_info()[0]['title'], 'R')
        self.assertFalse(p._recommended_queue)
        p.next_track()
        self.assertEqual(p._current_track['title'], 'R')
        p.next_track()
        self.assertEqual(p._current_track['title'], 'Already queued')
        p.next_track()
        self.assertEqual(p._current_track['title'], 'B')
        page.close()

    def test_queue_view_has_two_panels(self):
        page = QueuePage(self.player)
        page.refresh()
        self.assertEqual(page.splitter.count(), 2)
        self.assertIsNot(page.playlist_scroll, page.recommended_scroll)
        page.close()

    def test_late_recommendations_resume_after_natural_end(self):
        p = self.player
        p.play_queue([song('A')])
        p._on_track_ended()
        self.assertTrue(p._awaiting_recommendations)
        p.set_recommended_queue([song('R')])
        self.assertEqual(p._current_track['title'], 'R')
        self.assertFalse(p._awaiting_recommendations)

    def test_manual_stop_prevents_late_recommendations_from_autoplaying(self):
        p = self.player
        p.play_queue([song('A')])
        p._on_track_ended()
        p.stop()
        p.set_recommended_queue([song('R')])
        self.assertEqual(p._current_track['title'], 'A')
        self.assertEqual(len(p._recommended_queue), 1)

    def test_single_track_continues_with_recommendations(self):
        p = self.player
        p.play_queue([song('A')])
        p.set_recommended_queue([song('R')])
        p.next_track()
        self.assertEqual(p._current_track['title'], 'R')
        self.assertEqual(p._current_track_source, 'recommended')

    def test_shuffle_finishes_before_recommendations(self):
        p = self.player
        p.play_queue([song('A'), song('B'), song('C')])
        p.toggle_shuffle()
        p.set_recommended_queue([song('R')])
        played = [p._pop_next_track()[0]['title'] for _ in range(3)]
        self.assertEqual(set(played[:2]), {'B', 'C'})
        self.assertEqual(played[2], 'R')

    def test_repeat_all_keeps_playlist_before_recommendations(self):
        p = self.player
        p.play_queue([song('A')])
        p.set_recommended_queue([song('R')])
        p.toggle_repeat()
        p.next_track()
        self.assertEqual(p._current_track['title'], 'A')
        self.assertEqual(len(p._recommended_queue), 1)

    def test_promote_into_priority_and_do_not_restore_on_refresh(self):
        p = self.player
        p.play_queue([song('A'), song('B')])
        p.add_to_queue(song('P'))
        p.set_recommended_queue([song('R'), song('S')])
        self.assertTrue(p.promote_recommended(0, 'priority', 0, track_key(song('R'))))
        self.assertEqual([t['title'] for t in p._priority_queue], ['R', 'P'])
        p.set_recommended_queue([song('R'), song('S')])
        self.assertEqual([t['title'] for t in p._recommended_queue], ['S'])

    def test_promote_into_playlist_does_not_edit_saved_data(self):
        original = [song('A'), song('B'), song('C')]
        p = self.player
        p.play_queue(original)
        p.set_recommended_queue([song('R')])
        p.promote_recommended(0, 'base', 1)
        self.assertEqual([t['title'] for t in original], ['A', 'B', 'C'])
        self.assertEqual([t['title'] for t in p._base_queue], ['A', 'B', 'R', 'C'])

    def test_promote_into_shuffled_playlist(self):
        p = self.player
        p.play_queue([song('A'), song('B')])
        p.toggle_shuffle()
        p.set_recommended_queue([song('R')])
        p.promote_recommended(0, 'base', 0)
        self.assertEqual(p._get_next_track_info()[0]['title'], 'R')
        self.assertEqual(len(p._base_queue), 3)

    def test_live_refresh_does_not_destroy_drag_source(self):
        p = self.player
        p.set_recommended_queue([song('R')])
        page = QueuePage(p)
        page.refresh()
        original = page._cards[0]
        page._on_drag_state_changed(True)
        p.set_recommended_queue([song('Updated')])
        page.refresh()
        self.assertIs(page._cards[0], original)
        self.assertTrue(page._refresh_pending)
        page._on_drag_state_changed(False)
        app.processEvents()
        self.assertEqual(page._cards[0].track['title'], 'Updated')
        page.close()

    def test_drag_identity_survives_recommendation_reordering(self):
        p = self.player
        p.set_recommended_queue([song('R'), song('S')])
        p.set_recommended_queue([song('S'), song('R')])
        self.assertTrue(p.promote_recommended(0, 'priority', 0, track_key(song('R'))))
        self.assertEqual(p._priority_queue[0]['title'], 'R')

    def test_stale_drag_does_not_move_another_song(self):
        p = self.player
        p.set_recommended_queue([song('Changed')])
        self.assertFalse(p.promote_recommended(0, 'priority', 0, track_key(song('Old'))))
        self.assertFalse(p._priority_queue)

    def test_recommendations_do_not_duplicate_existing_or_played_tracks(self):
        p = self.player
        p.play_queue([song('A')])
        p.add_to_queue(song('P'))
        p.set_recommended_queue([song('A'), song('P'), song('R'), song('R')])
        self.assertEqual(len(p._recommended_queue), 1)
        p.next_track()
        p.next_track()
        p.set_recommended_queue([song('R')])
        self.assertFalse(p._recommended_queue)

    def test_new_playlist_clears_previous_recommendations(self):
        p = self.player
        p.play_queue([song('A')])
        p.set_recommended_queue([song('R')])
        session = p._queue_session
        p.play_queue([song('New')])
        self.assertFalse(p._recommended_queue)
        self.assertGreater(p._queue_session, session)

    def test_context_uses_selected_playlist_not_whole_library(self):
        p = self.player
        p.play_queue([song('A', 'Chosen')])
        history = MagicMock(entries={})
        manager = PlaybackRecommendationManager(p, None, history)
        self.addCleanup(manager.shutdown)
        manager._profile = manager._make_profile()
        manager._cache = [song('Suggested', 'Chosen'), song('Unrelated', 'Other')]
        manager._publish()
        self.assertEqual([t['title'] for t in p._recommended_queue], ['Suggested'])

    def test_late_results_from_previous_session_are_ignored(self):
        p = self.player
        p.play_queue([song('A')])
        manager = PlaybackRecommendationManager(p, None, MagicMock(entries={}))
        self.addCleanup(manager.shutdown)
        manager._profile = manager._make_profile()
        p.play_queue([song('New', 'Other')])
        manager._receive([song('Stale')])
        manager._publish()
        self.assertFalse(manager._candidates)
        self.assertFalse(p._recommended_queue)

    def test_crossfade_selects_recommendations_after_playlist(self):
        p = self.player
        p.play_queue([song('A')])
        p.set_recommended_queue([song('R')])
        p._start_crossfade(3)
        self.assertEqual(p._current_track['title'], 'R')
        self.assertFalse(p._recommended_queue)


class DropEvent:
    def __init__(self, card, y=0):
        self.card = card
        self.mime = QMimeData()
        self.mime.setData(QUEUE_MIME, json.dumps({'queue': card.queue_type,
                         'index': card.index, 'key': track_key(card.track)}).encode())
        self.y = y
        self.accepted = False

    def source(self): return self.card
    def mimeData(self): return self.mime
    def position(self): return QPointF(0, self.y)
    def acceptProposedAction(self): self.accepted = True
    def ignore(self): self.accepted = False


class DragTests(unittest.TestCase):
    def test_drop_into_empty_main_queue(self):
        container = DropContainer('priority')
        card = QueueTrackCard(song('R'), 0, 'recommended')
        event = DropEvent(card)
        received = []
        container.recommendation_dropped.connect(lambda *args: received.append(args))
        container.dropEvent(event)
        self.assertTrue(event.accepted)
        self.assertEqual(received, [(0, 0, track_key(song('R')))])

    def test_reorder_to_end_adjusts_removed_index(self):
        container = DropContainer('priority')
        for i in range(3):
            container.layout.addWidget(QueueTrackCard(song(str(i)), i, 'priority'))
        container.resize(500, 250)
        container.show()
        app.processEvents()
        card = container.layout.itemAt(0).widget()
        received = []
        container.item_moved.connect(lambda *args: received.append(args))
        container.dropEvent(DropEvent(card, 1000))
        self.assertEqual(received, [(0, 2)])
        container.close()

    def test_drag_does_not_start_playback(self):
        card = QueueTrackCard(song('R'), 0, 'recommended')
        card.resize(500, 94)
        card.show()
        app.processEvents()
        self.addCleanup(card.close)
        clicked = []
        card.play_clicked.connect(clicked.append)
        QTest.mousePress(card, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
        self.assertFalse(clicked)
        with patch('ui.queue_page.QDrag') as drag:
            event = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(100, 20), QPointF(100, 20),
                                Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            card.mouseMoveEvent(event)
            drag.return_value.exec.assert_called_once()
        QTest.mouseRelease(card, Qt.MouseButton.LeftButton)
        self.assertFalse(clicked)

    def test_external_text_drop_is_rejected(self):
        container = DropContainer('priority')
        event = DropEvent(QueueTrackCard(song('R'), 0, 'recommended'))
        event.mime.clear()
        event.mime.setText('recommended:0')
        container.dropEvent(event)
        self.assertFalse(event.accepted)
