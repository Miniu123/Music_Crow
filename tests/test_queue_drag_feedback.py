import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QMouseEvent, QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from core.player import MusicPlayer
from core.recommendations import track_key
from ui.queue_page import QueuePage, QueueTrackCard, DropContainer
from test_queue_recommendations import song, DropEvent

app = QApplication.instance() or QApplication([])


class QueueEditingTests(unittest.TestCase):
    def setUp(self):
        patcher = patch('core.player.mpv.MPV', side_effect=[MagicMock(), MagicMock()])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.player = MusicPlayer()
        self.player._poll_timer.stop()
        self.player.prefetcher.request = MagicMock()  # Drag tests must not download audio.
        self.addCleanup(self.player.shutdown)
        self.player.play_queue([song('A'), song('B'), song('C'), song('D')])

    def page(self):
        page = QueuePage(self.player)
        self.addCleanup(page.close)
        page.resize(1000, 650)
        page.refresh()
        page.show()
        app.processEvents()
        return page

    def test_move_playlist_track_to_priority_without_playing_or_losing_tracks(self):
        p = self.player
        p.add_to_queue(song('P'))
        self.assertTrue(p.move_queue_item('base', 1, 'priority', 0, track_key(song('C')), p.queue_edit_snapshot()))
        self.assertEqual(p._current_track['title'], 'A')
        self.assertEqual([t['title'] for t in p._priority_queue], ['C', 'P'])
        self.assertEqual([t['title'] for t in p.upcoming_base_tracks()], ['B', 'D'])
        for title in ('C', 'P', 'B', 'D'):
            p.next_track()
            self.assertEqual(p._current_track['title'], title)

    def test_priority_track_can_move_between_playlist_tracks(self):
        p = self.player
        p.add_to_queue(song('P'))
        p.move_queue_item('priority', 0, 'base', 1)
        self.assertFalse(p._priority_queue)
        self.assertEqual([t['title'] for t in p.upcoming_base_tracks()], ['B', 'P', 'C', 'D'])

    def test_moved_and_consumed_track_is_not_recommended_again(self):
        p = self.player
        p.move_queue_item('base', 0, 'priority', 0)
        p.next_track()
        p.next_track()
        p.set_recommended_queue([song('B')])
        self.assertFalse(p._recommended_queue)

    def test_stale_snapshot_distinguishes_entries_with_the_same_url(self):
        p = self.player
        p.play_queue([song('A'), dict(song('Same'), title='First'), dict(song('Same'), title='Second')])
        snapshot = p.queue_edit_snapshot()
        p.move_queue_item('base', 0, 'base', 2)
        self.assertFalse(p.move_queue_item('base', 0, 'priority', 0, track_key(song('Same')), snapshot))
        self.assertFalse(p._priority_queue)

    def test_reorder_boundary_matches_both_directions_and_end(self):
        p = self.player
        p.move_queue_item('base', 0, 'base', 3)
        self.assertEqual([t['title'] for t in p.upcoming_base_tracks()], ['C', 'D', 'B'])
        p.move_queue_item('base', 2, 'base', 0)
        self.assertEqual([t['title'] for t in p.upcoming_base_tracks()], ['B', 'C', 'D'])
        p.move_queue_item('base', 1, 'base', 2)
        self.assertEqual([t['title'] for t in p.upcoming_base_tracks()], ['B', 'C', 'D'])

    def test_shuffle_removal_remaps_indices_and_keeps_current_anchor(self):
        p = self.player
        p.play_queue([song('A'), song('B'), song('C'), song('D')], 2)
        p.toggle_shuffle()
        p._shuffled_indices = [0, 3, 1]
        p.move_queue_item('base', 0, 'priority', 0)
        self.assertEqual(p._current_base_index, 1)
        self.assertEqual(p._current_track['title'], 'C')
        self.assertEqual([t['title'] for t in p.upcoming_base_tracks()], ['D', 'B'])
        p.move_queue_item('priority', 0, 'base', 1)
        self.assertEqual([t['title'] for t in p.upcoming_base_tracks()], ['D', 'A', 'B'])
        self.assertEqual(len(set(p._shuffled_indices)), 3)

    def test_track_end_during_drag_rejects_stale_source_and_destination(self):
        page = self.page()
        card = next(c for c in page._cards if c.queue_type == 'base' and c.index == 1)
        page._on_drag_state_changed(True)
        self.player.next_track()
        event = DropEvent(card)
        page._pri_container.dropEvent(event)
        self.assertFalse(event.accepted)
        self.assertFalse(self.player._priority_queue)
        self.assertEqual(self.player._current_track['title'], 'B')
        page._on_drag_state_changed(False)

    def test_recommended_drop_checks_destination_after_playback_advances(self):
        p = self.player
        p.set_recommended_queue([song('R')])
        snapshot = p.queue_edit_snapshot()
        p.next_track()
        self.assertFalse(p.move_queue_item('recommended', 0, 'base', 1, track_key(song('R')), snapshot))
        self.assertEqual(p._recommended_queue[0]['title'], 'R')

    def test_recommendation_refresh_preserves_drag_identity(self):
        p = self.player
        p.set_recommended_queue([song('R'), song('S')])
        page = self.page()
        card = next(c for c in page._cards if c.queue_type == 'recommended')
        page._on_drag_state_changed(True)
        p.set_recommended_queue([song('S'), song('R')])
        event = DropEvent(card)
        page._pri_container.dropEvent(event)
        self.assertTrue(event.accepted)
        self.assertEqual(p._priority_queue[0]['title'], 'R')
        page._on_drag_state_changed(False)

    def test_stale_remove_and_play_actions_do_not_target_other_tracks(self):
        p = self.player
        p.add_to_queue(song('P'))
        p.add_to_queue(song('Q'))
        page = self.page()
        card = next(c for c in page._cards if c.queue_type == 'priority')
        p.next_track()
        page._remove_card(card)
        page._play_card(card)
        self.assertEqual(p._current_track['title'], 'P')
        self.assertEqual([t['title'] for t in p._priority_queue], ['Q'])

    def test_press_protects_card_before_drag_threshold_is_reached(self):
        page = self.page()
        card = next(c for c in page._cards if c.queue_type == 'base')
        QTest.mousePress(card, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
        self.assertTrue(page._drag_active)
        self.player.next_track()
        page.refresh()
        self.assertIn(card, page._cards)
        QTest.mouseRelease(card, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
        self.assertFalse(page._drag_active)
        self.assertEqual(self.player._current_track['title'], 'B')

    def test_all_tracks_are_visible_and_refresh_preserves_scroll(self):
        p = self.player
        p.play_queue([song(str(i)) for i in range(130)])
        page = self.page()
        self.assertEqual(len([c for c in page._cards if c.queue_type == 'base']), 129)
        bar = page.playlist_scroll.verticalScrollBar()
        bar.setValue(500)
        position = bar.value()
        p.set_recommended_queue([song('R')])
        page.refresh()
        app.processEvents()
        self.assertEqual(bar.value(), position)

    def send_drag_position(self, page, source, point):
        # Use actual Qt event delivery; no global cursor mocks. This is also
        # how the scroll controller gets its position during native Wayland DnD.
        mime = DropEvent(source).mime
        event = QDragEnterEvent(point, Qt.DropAction.MoveAction, mime,
                                Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(page.playlist_scroll.viewport(), event)

    def test_drag_scroll_continues_using_drag_event_position(self):
        self.player.play_queue([song(str(i)) for i in range(40)])
        page = self.page()
        source = next(c for c in reversed(page._cards) if c.queue_type == 'base')
        bar = page.playlist_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        before = bar.value()
        page._on_drag_state_changed(True)
        page._begin_drag_scroll(source)
        self.send_drag_position(page, source, QPoint(100, 5))
        for _ in range(8):
            page._scroll_during_drag()
        self.assertLess(bar.value(), before - 200)
        self.assertTrue(page._drag_scroll_timer.isActive())
        page._on_drag_state_changed(False)
        self.assertFalse(page._drag_scroll_timer.isActive())

    def test_drag_scroll_pauses_in_middle_and_outside_queue(self):
        self.player.play_queue([song(str(i)) for i in range(40)])
        page = self.page()
        source = next(c for c in page._cards if c.queue_type == 'base')
        bar = page.playlist_scroll.verticalScrollBar()
        bar.setValue(400)
        page._on_drag_state_changed(True)
        page._begin_drag_scroll(source)
        viewport = page.playlist_scroll.viewport()
        for point in (viewport.rect().center(), QPoint(-100, 5), QPoint(100, -150)):
            self.send_drag_position(page, source, point)
            page._scroll_during_drag()
            self.assertEqual(bar.value(), 400)
        page._on_drag_state_changed(False)

    def test_drag_timer_survives_native_mouse_release_and_stationary_pointer(self):
        self.player.play_queue([song(str(i)) for i in range(40)])
        page = self.page()
        source = next(c for c in reversed(page._cards) if c.queue_type == 'base')
        bar = page.playlist_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        before = bar.value()
        QTest.mousePress(source, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
        def native_drag(*_):
            self.send_drag_position(page, source, QPoint(100, 5))
            QTest.mouseRelease(source, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
            self.assertTrue(page._drag_scroll_timer.isActive())
            self.assertTrue(page._drag_active)
            QTest.qWait(150)
        with patch('ui.queue_page.QDrag') as drag:
            drag.return_value.exec.side_effect = native_drag
            event = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(100, 20), QPointF(100, 20),
                                Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            source.mouseMoveEvent(event)
        self.assertLess(bar.value(), before - 60)
        self.assertFalse(page._drag_scroll_timer.isActive())
        self.assertTrue(page._base_container.drop_indicator.isHidden())
        self.assertEqual(self.player._current_track['title'], '0')

    def test_bottom_edge_scrolls_down_and_drop_stops_timer(self):
        self.player.play_queue([song(str(i)) for i in range(40)])
        page = self.page()
        source = next(c for c in page._cards if c.queue_type == 'base')
        page._on_drag_state_changed(True)
        page._begin_drag_scroll(source)
        self.send_drag_position(page, source, QPoint(100, page.playlist_scroll.viewport().height() - 5))
        bar = page.playlist_scroll.verticalScrollBar()
        for _ in range(8):
            page._scroll_during_drag()
        self.assertGreater(bar.value(), 200)
        mime = DropEvent(source).mime
        drop = QDropEvent(QPointF(100, 5), Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        page.eventFilter(page.playlist_scroll.viewport(), drop)
        self.assertFalse(page._drag_scroll_timer.isActive())
        page._on_drag_state_changed(False)

    def test_leaving_queue_clears_drag_position(self):
        self.player.play_queue([song(str(i)) for i in range(40)])
        page = self.page()
        source = next(c for c in page._cards if c.queue_type == 'base')
        page._on_drag_state_changed(True)
        page._begin_drag_scroll(source)
        self.send_drag_position(page, source, QPoint(100, 5))
        page.eventFilter(page.playlist_scroll.viewport(), QDragLeaveEvent())
        self.assertIsNone(page._drag_position)
        page._on_drag_state_changed(False)

    def test_qt_viewport_drop_after_auto_scroll_uses_new_visible_position(self):
        self.player.play_queue([song(str(i)) for i in range(40)])
        page = self.page()
        source = next(c for c in reversed(page._cards) if c.queue_type == 'base')
        bar = page.playlist_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        page._on_drag_state_changed(True)
        page._begin_drag_scroll(source)
        viewport = page.playlist_scroll.viewport()
        point = QPoint(100, 5)
        self.send_drag_position(page, source, point)
        for _ in range(10):
            page._scroll_during_drag()
        position = page._base_container._drop_position
        self.assertIsNotNone(position)
        mime = DropEvent(source).mime
        drop = QDropEvent(QPointF(point), Qt.DropAction.MoveAction, mime,
                          Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(viewport, drop)
        self.assertTrue(drop.isAccepted())
        self.assertEqual(self.player.upcoming_base_tracks()[position]['title'], '39')
        self.assertEqual(self.player._current_track['title'], '0')
        self.assertFalse(page._drag_scroll_timer.isActive())
        page._on_drag_state_changed(False)


class DropFeedbackTests(unittest.TestCase):
    def container(self):
        container = DropContainer('base')
        self.addCleanup(container.close)
        for i in range(3):
            container.layout.addWidget(QueueTrackCard(song(str(i)), i, 'base'))
        container.resize(500, 240)
        container.show()
        app.processEvents()
        return container

    def test_indicator_tracks_boundaries_without_moving_cards(self):
        container = self.container()
        cards = container._cards()
        before = [card.geometry() for card in cards]
        source = QueueTrackCard(song('R'), 0, 'recommended')
        for y, expected in ((0, 0), (cards[1].y(), 1), (1000, 3)):
            event = DropEvent(source, y)
            container.dragMoveEvent(event)
            self.assertTrue(event.accepted)
            self.assertEqual(container._drop_position, expected)
            self.assertFalse(container.drop_indicator.isHidden())
            self.assertEqual([card.geometry() for card in cards], before)
        container.clear_drag()
        self.assertTrue(container.drop_indicator.isHidden())
        self.assertIsNone(container._drop_position)

    def test_drop_uses_same_position_as_marker_and_clears_it(self):
        container = self.container()
        source = QueueTrackCard(song('R'), 0, 'recommended')
        event = DropEvent(source, container._cards()[1].y())
        received = []
        container.recommendation_dropped.connect(lambda *args: received.append(args))
        container.dragMoveEvent(event)
        expected = container._drop_position
        container.dropEvent(event)
        self.assertEqual(received[0][1], expected)
        self.assertTrue(container.drop_indicator.isHidden())

    def test_invalid_drag_clears_previous_marker(self):
        container = self.container()
        source = QueueTrackCard(song('R'), 0, 'recommended')
        event = DropEvent(source)
        container.dragEnterEvent(event)
        event.mime.clear()
        container.dragMoveEvent(event)
        self.assertFalse(event.accepted)
        self.assertTrue(container.drop_indicator.isHidden())

    def test_empty_queue_has_an_insertion_marker(self):
        container = DropContainer('priority')
        self.addCleanup(container.close)
        container.resize(300, 60)
        container.show()
        event = DropEvent(QueueTrackCard(song('R'), 0, 'recommended'))
        container.dragMoveEvent(event)
        self.assertEqual(container._drop_position, 0)
        self.assertFalse(container.drop_indicator.isHidden())

