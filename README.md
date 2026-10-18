# Music Crow

A desktop music player built with Python and PyQt6. Search for tracks on YouTube Music and SoundCloud, store playlists locally, and use playback queues, an equalizer, and crossfade transitions.

## Getting started

Requires Python 3.10 or later and the system **libmpv** library (the mpv/libmpv package, depending on your distribution).

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
bash start.sh
```

The startup script uses the first available interpreter in this order: `.venv`, `venv`, then the system `python3`. Searches run yt-dlp through the application's Python interpreter. An internet connection is required to search and play online sources. Track availability depends on the source services.

The startup screen uses a soft logo reveal, animated sound bars, and your selected accent color. It transitions to the main window once initialization completes; clicking skips the animation's minimum display time without interrupting loading.

Playlists, covers, and settings are stored in `~/.config/music-crow/`. Media key integration through MPRIS is optional and requires `dbus-python`, PyGObject, and a D-Bus session. Google Drive backups can be enabled in settings after configuring Google sign-in (see below).

## Verification

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q core ui main.py
```

Tests cover playlist persistence (including interrupted writes), playback queues, stopping both mpv instances, search process timeouts, and thumbnail rendering. They do not require network access.

## Home page recommendations

The “Recommended for you” section combines tracks from your playlists and listening history with new search results for your favourite artists. Clicking a recommendation plays the list, while the `+` button lets you add a track to a queue or playlist.

Listening history records one play per session after 30 seconds of actual playback, or halfway through a shorter track (with a minimum of 5 seconds). Pausing, loading, and seeking do not increase the counter. History is stored locally in `~/.config/music-crow/listening_history.json` and includes up to 500 tracks. It does not include plays from before this feature was introduced.

The algorithm assigns 2 points for playlist membership, adds a weight based on play count, and halves the history weight every 30 days. Recommendations are limited to two tracks per artist and exclude the currently playing track. Discovery uses up to three artists and searches YouTube Music or SoundCloud. Only queries containing the artist's name are sent to these services; history remains local unless you enable its inclusion in backups to your own Google Drive. Recommendations from your library remain available offline. Discovery results are cached in memory for 30 minutes; the “Refresh” button fetches them again.

### Two playback queues

The queue view has two independently scrollable panels: “From playlist” and “Recommended”. The left panel shows tracks added to play next, followed by the remaining tracks in the selected playlist. The right panel contains matching recommendations that play automatically after the left queue finishes. Playback also starts automatically if recommendations arrive after the playlist has ended. Manually stopping playback prevents this automatic restart. When playlist repeat is enabled, recommendations wait until repeat is turned off.

The “Next →” button on a recommendation moves the track to the front of the left queue without interrupting the current track. You can also drag it to the beginning or a specific position among the remaining playlist tracks. This changes the current session without modifying the saved playlist. Clicking a card plays the track immediately, and the `✕` button removes it from the queue. Selecting a different playlist clears the previous recommendations for continued playback. On the home page, recommendations appear below your playlists.

While dragging, a bright insertion line marks exactly where the track will be placed. Hold the dragged track near the top or bottom edge to scroll continuously, even without moving the mouse. The scroll direction follows the top or bottom edge of the visible list, using drag-event coordinates so it does not depend on global cursor tracking. Scrolling gets faster closer to the edge and stops when the drag ends. Tracks can move between the play-next section and the remaining playlist, and list refreshes preserve your scroll position. If playback or another action changes the main queue during a drag, the outdated drop is cancelled to avoid moving the wrong entry. The view includes all remaining playlist tracks.

## Preparing the next track

By default, the application downloads audio for **one upcoming track** in the background, following the actual playback queue. This accounts for “Play next”, reordering, shuffle, repeat, and recommendations. Changing the next track cancels any download that is no longer needed. Both normal playback and crossfade use the prepared file; if it is unavailable, the player uses the original online source. The first track may still take a moment to load, and a slow connection may prevent the next track from being ready before the current one ends.

Preparation status appears below the playback slider. You can disable this feature in **Settings → Playback & sound → Prepare the next track**. Files are stored in `~/.cache/music-crow/audio/`. The cache is automatically trimmed to the three most recent files and approximately 200 MB, while protecting the current and upcoming files. Each file is limited to 80 MB. Prefetching skips live streams and recordings longer than 20 minutes. It does not save tracks to playlists or your downloads folder.

## Interface language and saving recommendations

In **Settings → Language → Application language**, choose **Polski** or **English**. The interface switches immediately, without restarting the application or interrupting playback. Your choice is saved in `theme.json`; changing the theme does not reset it. Playlist names, track titles, and artist names remain in their original form.

In the right-hand “Recommended” queue, the **Add to playlist** icon appears beside the “Next” button. Select an existing playlist or choose **Create a new playlist…**. Saving does not interrupt playback or move the track out of the queue. Tracks already saved are marked in the menu and are not added again. The same playlist picker is available for home page recommendations and search results.

## Browsing an artist or channel

Click the artist's name below a track in search results, a playlist, recommendations, or the bottom player bar to open their channel inside the application. The view shows tracks from the YouTube channel or SoundCloud profile in batches of 30; **Show more** loads the next batch. You can play the entire loaded list, start from a selected track, or use `+` to add a track to a queue or playlist. **Back** returns to the previous screen. Browsing alone does not interrupt music or change the queue.

New search results and imports retain the channel address. For older entries, the application tries to retrieve it from the track's URL. If the channel cannot be identified, it shows clearly labelled search results for the artist's name on the same platform; these may include recordings from other channels. Content depends on the source's public availability, and the channel publishing a track does not always belong to its artist. Loading runs in the background; switching to another artist cancels the previous request.

## Google Drive

**Settings → Google Drive** provides Google sign-in, automatic backups, **Back up now**, **Restore backup…**, and sign-out. Network requests and sign-in waiting run in the background; **Cancel** stops waiting. The session resumes when you restart the application. Your local library remains usable offline.

### One-time Google configuration

Google requires a registered OAuth client for the application. This repository does not include the author's configuration or account, so you need to set up your own project once:

1. In [Google Cloud Console](https://console.cloud.google.com/), create or select a project and enable **Google Drive API** in the API library.
2. Configure **Google Auth Platform / the OAuth consent screen** with an application name and contact email. If the application is in testing mode, add your Google email address to the test users.
3. Under data access, add the `https://www.googleapis.com/auth/drive.appdata` scope.
4. Create an **OAuth Client ID → Desktop app** and download the client JSON file.
5. Start the application with `bash start.sh`. In settings, click **Choose Google configuration…**, select the downloaded JSON file, and choose **Sign in with Google**. Complete the consent flow in your system browser.
6. On another computer, configure a client from the same Google project and sign in to the same account, then select **Restore backup…**.

Official Google instructions: [OAuth for desktop applications](https://developers.google.com/identity/protocols/oauth2/native-app) and [application data on Drive](https://developers.google.com/workspace/drive/api/guides/appdata).

### What is backed up

Backups include playlists, covers, and language, appearance, and playback settings. Listening history can be included using a separate toggle (disabled by default). Audio files, caches, sign-in credentials, and OAuth configuration are not uploaded. Each backup is limited to 40 MB, and each cover to 5 MB.

Backups are stored in Google Drive's private **appDataFolder**, rather than the visible “My Drive” folder. The application requests only the `drive.appdata` scope. The configuration file is stored locally as `~/.config/music-crow/credentials.json`, and the session token as `google_token.json`, with owner-only permissions. Signing out removes the local token without deleting data from Drive. You can also revoke the application's access in your Google account settings.

### Saving and restoring

Automatic backup runs 3 seconds after changes and checks the data every 5 minutes. Identical data is not uploaded again. Each installation updates its own backup file; backups from other devices remain separate. This is a backup system with manual restoration, without automatic overwriting of libraries across devices. **Back up now** also works when automatic backups are disabled.

Restoration first downloads and validates the entire backup, then shows the playlist and track counts for confirmation. Current data is saved to `~/.config/music-crow/recovery/`. Settings are restored, while playlists are added without deleting existing ones. A different playlist with the same name receives the **(Google Drive)** suffix; an identical playlist is not duplicated. Listening history is merged without counting the same plays again. Cover paths are adjusted for the current computer. Changes take effect without a restart and do not interrupt playback.

OAuth/Drive protocol tests use controlled responses and cover PKCE, sign-in state validation, cancellation, access scopes, per-device files, data restoration, and rollback after a write failure. A full test with a real account requires your own OAuth file and consent in the browser.
