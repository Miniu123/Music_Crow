import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'app/src/main/python'))
from recommendations import recommend_tracks, artist_name, track_key


def song(key, artist, title=None, **extra):
    return dict(url='https://youtu.be/' + key, title=title or key, artist=artist,
                uploader=artist, duration=180, **extra)


class SessionRecommendationsTests(unittest.TestCase):
    def recommend(self, **kwargs):
        return recommend_tracks(kwargs.pop('groups', []), kwargs.pop('history', {}), **kwargs)

    def test_new_single_outranks_unrelated_heavy_listening_history(self):
        current = song('current', 'New artist')
        old = song('old', 'Old favourite')
        result = self.recommend(context=[current], discoveries=[song('new', 'New artist'), old],
                                history={'old': dict(track=old, plays=10000, last_played=0)})
        self.assertEqual([t['url'] for t in result['tracks']], ['https://youtu.be/new'])
        self.assertEqual(result['seeds'], ['New artist'])

    def test_current_recording_and_alternate_upload_excluded_without_library(self):
        current = song('current', 'Artist', 'Evening (Official Audio)')
        alternate = song('alternate', 'Artist', 'Evening [Official Video]')
        next_song = song('next', 'Artist', 'Another song')
        result = self.recommend(context=[current], discoveries=[current, alternate, next_song])
        self.assertEqual([t['url'] for t in result['tracks']], [next_song['url']])

    def test_one_artist_limit_across_library_and_discovery(self):
        local = [song('local' + str(i), 'Artist') for i in range(6)]
        fresh = [song('fresh' + str(i), 'Artist') for i in range(6)]
        result = self.recommend(groups=[local], context=[song('current', 'Artist')], discoveries=fresh)
        self.assertEqual(len(result['tracks']), 3)
        self.assertEqual(len({track_key(t) for t in result['tracks']}), 3)

    def test_artist_credit_beats_lyrics_channel_uploader(self):
        current = dict(url='https://youtu.be/current', title='Real Artist - Evening (Lyrics)', uploader='Lyrics Channel')
        self.assertEqual(artist_name(current), 'Real Artist')
        result = self.recommend(context=[current], discoveries=[song('next', 'Real Artist'), song('wrong', 'Lyrics Channel')])
        self.assertEqual(result['seeds'], ['Real Artist'])
        self.assertEqual([t['url'] for t in result['tracks']], ['https://youtu.be/next'])

    def test_version_suffix_is_not_mistaken_for_an_artist_credit(self):
        self.assertEqual(artist_name(dict(title='Evening - Remastered 2024', uploader='Actual Artist')), 'Actual Artist')

    def test_new_single_featured_artist_is_a_discovery_seed(self):
        current = song('current', 'Main Artist', 'Night (feat. Guest Artist)')
        result = self.recommend(context=[current], discoveries=[song('guest', 'Guest Artist')])
        self.assertIn('Guest Artist', result['seeds'])
        self.assertEqual(len(result['tracks']), 1)

    def test_co_playlist_artist_is_relevant_but_unrelated_playlist_is_not(self):
        anchor = song('anchor', 'Artist A')
        friend = song('friend', 'Artist B')
        other = song('other', 'Artist C')
        result = self.recommend(groups=[[anchor, friend], [other]], context=[song('current', 'Artist A')])
        self.assertIn(friend['url'], [t['url'] for t in result['tracks']])
        self.assertNotIn(other['url'], [t['url'] for t in result['tracks']])

    def test_live_short_clips_and_albums_not_used_for_single_radio(self):
        candidates = [song('stream', 'Artist', is_live=True), song('clip', 'Artist'),
                      song('album', 'Artist', 'Full Album'), song('normal', 'Artist')]
        candidates[1]['duration'] = 20
        result = self.recommend(context=[song('current', 'Artist')], discoveries=candidates)
        self.assertEqual([t['url'] for t in result['tracks']], ['https://youtu.be/normal'])

    def test_queue_recording_excluded_even_at_different_url(self):
        queued = song('queued', 'Artist', 'Tomorrow')
        result = self.recommend(context=[song('current', 'Artist')], excluded=[queued],
                               discoveries=[song('mirror', 'Artist', 'Tomorrow (Official Audio)')])
        self.assertEqual(result['tracks'], [])

    def test_original_song_does_not_recommend_remixes_or_speed_edits(self):
        edits = [song('edit' + str(i), 'Artist', 'Night ' + version) for i, version in enumerate(
            ['(DJ Remix)', '(Remiks)', '(Bootleg)', '(Mashup)', '(Slowed + Reverb)',
             '(Sped Up)', '(Nightcore)', '(Bass Boosted)', '(Club Edit)'])]
        original = song('original', 'Artist', 'Morning (Official Audio)')
        result = self.recommend(context=[song('current', 'Artist')], discoveries=edits + [original])
        self.assertEqual([t['url'] for t in result['tracks']], [original['url']])

    def test_remix_context_can_still_recommend_remixes(self):
        remix = song('remix', 'Artist', 'Morning (Club Remix)')
        result = self.recommend(context=[song('current', 'Artist', 'Night (Remix)')], discoveries=[remix])
        self.assertEqual([t['url'] for t in result['tracks']], [remix['url']])

    def test_artist_name_in_unrelated_title_is_not_a_credit(self):
        wrong = song('wrong', 'Other Artist', 'Walking On Air')
        result = self.recommend(context=[song('current', 'Air')], discoveries=[wrong])
        self.assertEqual(result['tracks'], [])

    def test_featured_artist_credit_is_still_a_match(self):
        candidate = song('guest', 'Other Artist', 'Night (feat. Air)')
        result = self.recommend(context=[song('current', 'Air')], discoveries=[candidate])
        self.assertEqual([t['url'] for t in result['tracks']], [candidate['url']])

    def test_no_session_keeps_personal_library_recommendations(self):
        result = self.recommend(groups=[[song('a', 'Artist A'), song('b', 'Artist B')]])
        self.assertEqual(len(result['tracks']), 2)

if __name__ == '__main__': unittest.main()


class HomeRecommendationsTests(unittest.TestCase):
    """The home page asks without a current-song context: suggestions follow history."""

    def test_home_suggestions_follow_listening_history_not_the_current_song(self):
        now = __import__('time').time()
        history = {}
        for i, (artist, plays) in enumerate([('Taco Hemingway', 40), ('Taco Hemingway', 25),
                                             ('Kizo', 30), ('Majki', 12)]):
            track = song(f'hist{i}', artist)
            history[track_key(track)] = dict(track=track, plays=plays, last_played=now - 86400 * (20 + i))
        discoveries = [song('new-taco', 'Taco Hemingway'), song('new-other', 'Unrelated Band')]
        result = recommend_tracks([], history, context=[], discoveries=discoveries)
        artists = {artist_name(t) for t in result['tracks']}
        self.assertTrue({'Taco Hemingway', 'Kizo', 'Majki'} <= artists)  # many history artists
        urls = [t['url'] for t in result['tracks']]
        self.assertIn('https://youtu.be/new-taco', urls)        # discoveries matching taste
        self.assertNotIn('https://youtu.be/new-other', urls)    # nothing unrelated
        self.assertFalse(any(t['recommendation_reason'].startswith('Pasuje do teraz')
                             for t in result['tracks']))
        self.assertEqual(result['seeds'][0], 'Taco Hemingway')  # strongest history artist
