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

The recommendation engine combines saved tracks, listening frequency, a 30-day history half-life, and the current listening context. Scores use logarithmic weighting so a large collection by one artist does not completely dominate. Recently played songs receive a temporary penalty; older favourites can return. Playlist co-occurrence connects artists during playback, while explicit featured-artist credits provide a path to discovering collaborators. These are metadata-based signals, not audio, genre, or BPM analysis.

Discovery performs at most four sequential searches per manager, with up to 12 results per search. It keeps two strong artist anchors and rotates the remaining seeds through the taste profile. Refreshing also lowers the priority of previously displayed tracks for the current app session. Results are balanced across artists (at most two per artist on the home page, three in the continuation queue), with duplicate recordings recognised across common “official video”, audio and lyrics labels. Different live, remix and acoustic versions retain their identity. Unknown discoveries shorter than 45 seconds, longer than 20 minutes, live streams and common compilation titles are filtered out; saved library suggestions are not subject to that duration filter.

The home page mixes up to six discoveries with familiar tracks, filling up to eight places when enough artists and candidates are available. Playback suggestions stay anchored to the selected playlist and current track, excluding queued or already consumed tracks. Discovery pools are bounded to 240 tracks in memory, normally reused for 30 minutes; failed searches, empty pools and continuation queues with fewer than three suggestions can retry on the next refresh after a one-minute cooldown. Search wording rotates between music, songs and official audio. Offline library suggestions remain available. Only queries containing artist names are sent to YouTube Music or SoundCloud; history remains local unless you opt into history backups on your own Google Drive.

### Two playback queues

The queue view has two independently scrollable panels: “From playlist” and “Recommended”. The left panel shows tracks added to play next, followed by the remaining tracks in the selected playlist. The right panel contains matching recommendations that play automatically after the left queue finishes. Playback also starts automatically if recommendations arrive after the playlist has ended. Manually stopping playback prevents this automatic restart. When playlist repeat is enabled, recommendations wait until repeat is turned off.

The “Next →” button on a recommendation moves the track to the front of the left queue without interrupting the current track. You can also drag it to the beginning or a specific position among the remaining playlist tracks. This changes the current session without modifying the saved playlist. Clicking a card plays the track immediately, and the trash button removes any upcoming track from the current queue without changing the saved playlist. The currently playing track is kept separate. Selecting a different playlist clears the previous recommendations for continued playback. On the home page, recommendations appear below your playlists.

While dragging, a bright insertion line marks exactly where the track will be placed. Hold the dragged track near the top or bottom edge to scroll continuously, even without moving the mouse. The scroll direction follows the top or bottom edge of the visible list, using drag-event coordinates so it does not depend on global cursor tracking. Scrolling gets faster closer to the edge and stops when the drag ends. Tracks can move between the play-next section and the remaining playlist, and list refreshes preserve your scroll position. If playback or another action changes the main queue during a drag, the outdated drop is cancelled to avoid moving the wrong entry. The view includes all remaining playlist tracks. Removing a track updates playback immediately, then collapses its row with a short animation. Added or reordered rows receive a brief highlight, and the trash lid animates on hover. Player controls, navigation, and home actions have subtle hover and press feedback; page transitions also handle rapid navigation without leaving a page faded out.

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

### Publisher setup for Google sign-in

The publisher registers Music Crow once. In a configured release, users only click **Sign in with Google**, choose their account in the **default system browser**, and approve access. They do not need Google Cloud projects or JSON files. OAuth uses PKCE and a temporary loopback callback on `127.0.0.1`; no hosted authentication server is required. Saved tokens allow the session to resume on later launches.

This repository deliberately excludes the publisher's OAuth configuration. Until the publisher completes the following setup, sign-in is disabled with a clear explanation:

1. Open [Google Cloud Console](https://console.cloud.google.com/), create a project named **Music Crow**, and enable **Google Drive API** under **APIs & Services → Library**.
2. Open **Google Auth Platform**, select **Get started**, and enter the application name, support email, and developer contact. Choose **External** under **Audience** so accounts outside your organization can sign in. Add your own email as a test user while developing.
3. Under **Data Access**, add only `https://www.googleapis.com/auth/drive.appdata`. This non-sensitive scope grants access to the application's own hidden backup folder, rather than users' other Drive files.
4. Under **Clients → Create client**, choose **Desktop app** and name it **Music Crow Desktop**. Download the Desktop client JSON and save it as `core/google_oauth_client.json`. This file is ignored by Git; never paste its values into tracked source files. Only the publisher supplies this file. Do not choose a Web application client or enter website redirect URLs for this desktop flow.
5. Start Music Crow and test **Settings → Google Drive → Sign in with Google** with your test account. Test backup and restore too. Include `core/google_oauth_client.json` in the packaged application alongside the loader module. A Git clone or GitHub source archive does not include this ignored file, so its publisher must supply it to enable sign-in. End users of the configured release do not need to import a file. Desktop client identifiers are distributed with the app; user tokens, service-account keys, and web-server secrets must never be included in a release.
6. Before public distribution, complete **Branding**, including a public application homepage, privacy policy, and contact information. Change **Audience → Publishing status** from **Testing** to **In production / Publish app**. Complete the brand or other verification requested by Google. Testing mode is limited to allowlisted accounts and can expire refresh tokens after seven days; publishing and verification are distinct steps. Workspace administrators can still restrict access for their organizations.

Keep releases and devices on the same Google project so they can access the same application's backups. After signing in on another device, select **Restore backup…** to restore an existing backup.

For development or an existing personal setup, **Custom Google configuration (advanced)** still allows importing a Desktop OAuth JSON file. An explicitly imported local client takes precedence over the bundled client, preserving existing setups. This advanced control is hidden for a fresh installation with valid bundled credentials.

Official instructions: [OAuth for desktop applications](https://developers.google.com/identity/protocols/oauth2/native-app), [application data on Drive](https://developers.google.com/workspace/drive/api/guides/appdata), [OAuth publishing states](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview), and [production policy requirements](https://developers.google.com/identity/protocols/oauth2/production-readiness/policy-compliance).

### What is backed up

Backups include playlists, covers, and language, appearance, and playback settings. Listening history can be included using a separate toggle (disabled by default). Audio files, caches, sign-in credentials, and OAuth configuration are not uploaded. Each backup is limited to 40 MB, and each cover to 5 MB.

Each signed-in Google account has its own **music-crow-config.json** in Google Drive's private **appDataFolder**, rather than the visible “My Drive” folder. Settings, playlists, covers, and optional history are stored together in this file. Requests use that user's OAuth session, so different accounts have separate files even though the filename is the same. The application requests only the `drive.appdata` scope. The session token is stored locally as `~/.config/music-crow/google_token.json`, with owner-only permissions. An optional manually imported configuration is stored as `credentials.json` in the same directory; bundled releases do not require this file. Signing out removes the local token without deleting data from Drive. You can also revoke the application's access in your Google account settings.

### Saving and restoring

Automatic backup runs 3 seconds after changes and checks the data every 5 minutes. Identical local data is not uploaded again. Saves update the same account configuration file instead of creating a file per device. **Back up now** also works when automatic backups are disabled.

Before writing an existing file, the application compares its ID and content checksum with the last successfully uploaded or restored copy. A fresh installation, a different account, or a changed cloud copy pauses uploads and asks you to **Restore backup…** first. Merely downloading a copy or cancelling restoration does not acknowledge it for future writes. Restoration requires confirmation and retains a local recovery copy. This remains a backup system with manual restoration, not live bidirectional synchronization.

The checksum comparison is a preflight check, not an atomic multi-device lock: overlapping writes can still race. Avoid editing the same account on multiple devices simultaneously. Duplicate configuration files, if created by simultaneous first-time uploads, block further uploads rather than silently selecting one. Older per-device backups remain available for restoration and are not automatically deleted; new saves use only `music-crow-config.json`.

Restoration first downloads and validates the entire backup, then shows the playlist and track counts for confirmation. Current data is saved to `~/.config/music-crow/recovery/`. Settings are restored, while playlists are added without deleting existing ones. A different playlist with the same name receives the **(Google Drive)** suffix; an identical playlist is not duplicated. Listening history is merged without counting the same plays again. Cover paths are adjusted for the current computer. Changes take effect without a restart and do not interrupt playback.

OAuth/Drive protocol tests use controlled responses and cover PKCE, sign-in state validation, cancellation, access scopes, the shared account filename, account separation, stale-write detection, data restoration, and rollback after a write failure. A full test with a real account requires a registered Desktop OAuth client and consent in the browser. Tests also cover bundled configuration, missing or invalid publisher credentials, and compatibility with existing imported clients.

## Public website and privacy policy

The static website lives in [`docs/`](docs/README.md). It includes a Polish product homepage, a privacy policy describing local storage and optional Google Drive backups, and the public contact `minu3009@gmail.com`.

To publish it, push `docs/` to GitHub, then choose **Settings → Pages → Deploy from a branch → main → /docs → Save**. After a successful deployment, the expected homepage is `https://miniu123.github.io/Music_Crow/` and the privacy policy is `https://miniu123.github.io/Music_Crow/privacy.html`. See the website guide for OAuth branding, domain verification, and custom-domain setup. Publishing on Pages does not automatically complete Google's verification.
