# Music Crow Flatpak — first local release

The recipe targets Linux x86_64, app ID `io.github.Miniu123.MusicCrow`, version `0.1.0`, and Freedesktop Platform/SDK `25.08`. It includes PyQt6/Qt, libmpv with Lua and PulseAudio, yt-dlp with EJS and Deno, Google OAuth libraries, and MPRIS dependencies.

The sandbox uses network access for music/OAuth, Wayland or fallback X11, PulseAudio, graphics acceleration and its own MPRIS bus name. It does not require access to the entire home directory. File selection and opening the system browser use desktop portals. Settings and playlists use `XDG_CONFIG_HOME`; audio cache uses `XDG_CACHE_HOME`.

## Build

1. Install Flatpak, Flathub, `org.flatpak.Builder`, `org.freedesktop.Sdk//25.08` and `org.freedesktop.Platform//25.08`.
2. From the application repository, download wheels for the runtime Python:

```sh
python3 -m pip download --dest packaging/flatpak/wheels --only-binary=:all: --python-version 3.13 'PyQt6>=6.5,<7' python-mpv 'yt-dlp[default]' 'google-auth-oauthlib>=1.2,<2' requests Jinja2
python3 packaging/flatpak/download_sources.py
python3 packaging/flatpak/prepare.py '/path/to/build-directory' --with-google-client
bash '/path/to/build-directory/build.sh'
```

`--with-google-client` includes only the publisher's Desktop OAuth client from the ignored `core/google_oauth_client.json`. It must be supplied to make sign-in available in the release. User tokens, Google sessions, local playlists, caches, and `.git` are never copied. The Desktop OAuth client configuration can be extracted from the distributed package; do not use Web client credentials here.

The generated manifest pins downloaded archives and wheels by SHA-256 and builds offline. Keep the generated directory, source archives and wheels to reproduce this exact dependency set. Re-running dependency downloads from scratch can resolve newer versions. App source is copied from the working tree, including current fixes, not only committed Git files. The directory is a local release workspace, not a public source repository: its `app-source/core/google_oauth_client.json` contains publisher configuration.

## Install and run

```sh
flatpak install --user ./Music-Crow-0.1.0-x86_64.flatpak
flatpak run io.github.Miniu123.MusicCrow
```

The installer may download Freedesktop Platform dependencies from Flathub. This is a local `.flatpak` bundle, not a Flathub publication or an automatically updating repository.

Application data is stored under `~/.var/app/io.github.Miniu123.MusicCrow/config/music-crow/`; cache is under `~/.var/app/io.github.Miniu123.MusicCrow/cache/music-crow/`. The existing non-Flatpak library is not automatically imported. Sign in and restore your Google backup to transfer it.

## Verification

`smoke_test.py` checks the installed modules, silent MPV audio decoding, a real Qt main window, local settings/backup creation and presence of the publisher's OAuth configuration. It creates temporary test data; it does not sign in or upload to Google. Install the bundle first and run the test using `flatpak run`, which prepares the application's library cache. `flatpak build --runtime` does not reproduce that setup and can incorrectly report that libmpv is missing. Do not use the SDK to verify runtime dependencies.

From this repository, after installing the bundle:

```sh
flatpak run --env=QT_QPA_PLATFORM=offscreen \
  --filesystem="$PWD/packaging/flatpak:ro" \
  --command=python3 io.github.Miniu123.MusicCrow \
  "$PWD/packaging/flatpak/smoke_test.py" /tmp/music-crow-preview.png
```

The preview is written inside the Flatpak's temporary directory. OAuth consent and online service availability need a separate interactive check. The current MPRIS implementation may log D-Bus errors for unsupported desktop property queries; these do not prevent startup or audio decoding.

Upstream references: https://docs.flatpak.org/en/latest/first-build.html and https://docs.flatpak.org/en/latest/single-file-bundles.html.
