# Music Crow: licensing scope and third-party components

Copyright (c) 2026 Miniu123. The original Music Crow code and documentation
are licensed under MIT; see LICENSE. Third-party code, libraries and their
assets retain their own licenses. Music, artwork and other content accessed
through external services are not licensed by Music Crow.

## Distributed application

The current build uses the GPL-3.0-only edition of PyQt6. A combined
application distributed with this edition must comply with GPLv3, including
its Corresponding Source requirements. The MIT grant for the original Music
Crow code remains available; it does not make the whole binary package
MIT-only or remove the obligations of its dependencies.

Before distributing a binary release, provide the matching application and
dependency sources, build scripts, license texts and notices as required by
their licenses. A link to the latest application checkout alone is not a
complete source distribution for all bundled libraries. Preserve upstream
notices and check the exact components and build options in that release.

## Principal dependencies

The following is an overview, not an exhaustive inventory of the Flatpak
runtime, transitive dependencies or codecs. Exact terms are supplied by each
upstream project and the installed package's license files.

| Component | License / distribution notes | Upstream |
| --- | --- | --- |
| PyQt6 | GPL-3.0-only in the current wheel; a separate commercial license is available | https://www.riverbankcomputing.com/software/pyqt/intro |
| Qt 6 | LGPLv3 edition in the PyQt6-Qt6 wheel; individual modules and third-party components may have other terms | https://www.qt.io/licensing/open-source-lgpl-obligations |
| python-mpv | GPLv2-or-later or LGPLv2.1-or-later | https://github.com/jaseg/python-mpv |
| mpv / libmpv | GPLv2-or-later by default; the current recipe does not select the LGPL-only build option | https://github.com/mpv-player/mpv/blob/v0.40.0/Copyright |
| yt-dlp | Unlicense for the project; bundled and optional dependencies have separate terms | https://github.com/yt-dlp/yt-dlp#license |
| google-auth-oauthlib | Apache-2.0 | https://github.com/googleapis/google-auth-library-python-oauthlib |
| Requests | Apache-2.0 | https://github.com/psf/requests |

The Flatpak also includes or uses components such as Python, FFmpeg, Lua,
libass, libplacebo, Deno, PyGObject, dbus-python, Kerberos and the Freedesktop
runtime. Their licenses are not replaced by this project's MIT license.

## Commercial use and advertising

MIT permits commercial use, sale, modification and redistribution. Keeping
the copyright and license notice is required. Recipients may also distribute
modified versions, including versions that remove advertising.

GPLv3 also permits commercial distribution, subject to its conditions. Using
advertising does not itself require changing the license of Music Crow.
A proprietary distribution would require a different dependency licensing
strategy, including appropriate PyQt and libmpv licensing, not merely
changing the LICENSE file.

No advertising system is currently implemented. Any future advertising
integration must be assessed separately for service terms and privacy;
the software license does not grant rights to third-party media or Google
account data. The privacy policy must describe actual behavior.

References:
- https://choosealicense.com/licenses/mit/
- https://www.riverbankcomputing.com/commercial/license-faq
- https://www.gnu.org/licenses/gpl-faq.html#GPLCommercially
