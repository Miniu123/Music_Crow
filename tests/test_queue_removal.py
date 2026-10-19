import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QStackedWidget, QWidget

from core.player import MusicPlayer
from core.recommendations import track_key
from ui.queue_page import QueuePage
from ui.main_content import MainContent
from test_queue_recommendations import song

app = QApplication.instance() or QApplication([])


class QueueRemovalTests(unittest.TestCase):
    def setUp(self):
        patcher = patch('core.player.mpv.MPV', side_effect=[MagicMock(), MagicMock()])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.player = MusicPlayer()
        self.player._poll_timer.stop()
        self.player.prefetcher.request = MagicMock()
        self.addCleanup(self.player.shutdown)
        self.tracks = [song(name) for name in ('A', 'B', 'C', 'D')]
        self.player.play_queue(self.tracks)

    def page(self):
        page = QueuePage(self.player)
        self.addCleanup(page.close)
        page.resize(1000, 650)
        page.refresh()
        page.show()
        app.processEvents()
        return page

    def test_removal_changes_session_only_and_not_playing_track(self):
        p = self.player
        updates = []
        p.queue_updated.connect(lambda: updates.append(True))
        self.assertTrue(p.remove_queue_item('base', 0, track_key(song('B')), p.queue_edit_snapshot()))
        self.assertEqual(len(updates), 1)
        self.assertEqual(p._current_track['title'], 'A')
        self.assertEqual([t['title'] for t in self.tracks], ['A', 'B', 'C', 'D'])
        p.next_track()
        self.assertEqual(p._current_track['title'], 'C')
        p.set_recommended_queue([song('B'), song('R')])
        self.assertEqual([t['title'] for t in p._recommended_queue], ['R'])

    def test_shuffle_remaps_both_playing_index_and_remaining_order(self):
        p = self.player
        p.play_queue(self.tracks, start_index=3)
        p._shuffle = True
        p._shuffled_indices = [1, 0, 2]
        self.assertTrue(p.remove_queue_item('base', 0))
        self.assertEqual(p._current_base_index, 2)
        self.assertEqual(p._current_track['title'], 'D')
        self.assertEqual([t['title'] for t in p.upcoming_base_tracks()], ['A', 'C'])
        p.next_track()
        self.assertEqual(p._current_track['title'], 'A')
        p.next_track()
        self.assertEqual(p._current_track['title'], 'C')

    def test_stale_snapshot_and_invalid_actions_do_not_remove_neighbor(self):
        p = self.player
        snapshot = p.queue_edit_snapshot()
        p.next_track()
        self.assertFalse(p.remove_queue_item('base', 0, track_key(song('B')), snapshot))
        self.assertFalse(p.remove_queue_item('now_playing', 0))
        self.assertFalse(p.remove_queue_item('base', -1))
        self.assertEqual([t['title'] for t in p.upcoming_base_tracks()], ['C', 'D'])

    def test_duplicate_urls_are_distinguished_by_snapshot(self):
        p = self.player
        p.play_queue([song('A'), dict(song('X'), title='First'), dict(song('X'), title='Second')])
        snapshot = p.queue_edit_snapshot()
        self.assertTrue(p.remove_queue_item('base', 0, track_key(song('X')), snapshot))
        self.assertFalse(p.remove_queue_item('base', 0, track_key(song('X')), snapshot))
        self.assertEqual(p.upcoming_base_tracks()[0]['title'], 'Second')

    def test_recommendation_refresh_resolves_exact_track(self):
        p = self.player
        p.set_recommended_queue([song('R'), song('S')])
        snapshot = p.queue_edit_snapshot()
        p.set_recommended_queue([song('S'), song('R')])
        self.assertTrue(p.remove_queue_item('recommended', 0, track_key(song('R')), snapshot))
        self.assertEqual([t['title'] for t in p._recommended_queue], ['S'])

    def test_all_upcoming_sections_have_trash_and_current_track_does_not(self):
        self.player.add_to_queue(song('P'))
        self.player.set_recommended_queue([song('R')])
        page = self.page()
        for card in page._cards:
            self.assertEqual(hasattr(card, 'btn_remove'), card.queue_type != 'now_playing')

    def test_trash_commits_before_animation_and_survives_playback_update(self):
        p = self.player
        page = self.page()
        card = next(c for c in page._cards if c.queue_type == 'base')
        QTest.mouseClick(card.btn_remove, Qt.MouseButton.LeftButton)
        self.assertEqual([t['title'] for t in p.upcoming_base_tracks()], ['C', 'D'])
        self.assertEqual(p._current_track['title'], 'A')
        self.assertIs(page._removing_card, card)
        self.assertFalse(card.isEnabled())
        page._remove_card(card)  # A duplicate activation must not remove C.
        p.next_track()
        page.refresh()
        self.assertIn(card, page._cards)
        QTest.qWait(300)
        self.assertIsNone(page._removing_card)
        self.assertEqual(p._current_track['title'], 'C')
        self.assertEqual(page.playlist_count.text(), '1')
        self.assertEqual([c.track['title'] for c in page._cards if c.queue_type == 'base'], ['D'])

    def test_priority_removal_keeps_base_queue_intact(self):
        p = self.player
        p.add_to_queue(song('P'))
        self.assertTrue(p.remove_queue_item('priority', 0))
        self.assertEqual([t['title'] for t in p.upcoming_base_tracks()], ['B', 'C', 'D'])
        p.next_track()
        self.assertEqual(p._current_track['title'], 'B')


class PageTransitionTests(unittest.TestCase):
    def test_rapid_navigation_clears_interrupted_opacity_effects(self):
        owner = QWidget()
        owner.stack = QStackedWidget(owner)
        for _ in range(3):
            owner.stack.addWidget(QWidget())
        for index in (1, 2, 0, 1):
            MainContent._fade_to_page(owner, index)
        self.assertIsNone(owner.stack.widget(0).graphicsEffect())
        self.assertIsNone(owner.stack.widget(2).graphicsEffect())
        QTest.qWait(280)
        self.assertIsNone(owner.stack.widget(1).graphicsEffect())
        self.assertIsNone(owner._current_page_anim)
        owner.close()
        owner.deleteLater()


if __name__ == '__main__':
    unittest.main()
