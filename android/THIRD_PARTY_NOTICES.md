# Android dependencies

Music Crow's original sources retain the repository MIT license. The Android
port does not bundle PyQt6 or libmpv. Its direct dependencies include:

| Component | Version | License / source |
| --- | --- | --- |
| AndroidX Media3 | 1.6.1 | Apache-2.0; https://github.com/androidx/media |
| AndroidX Core | 1.15.0 | Apache-2.0; https://android.googlesource.com/platform/frameworks/support/ |
| Chaquopy | 17.1.0 | MIT; https://github.com/chaquo/chaquopy |
| Python runtime | 3.14 | PSF and included third-party notices; https://www.python.org/psf/license/ |
| yt-dlp | 2026.10.21 | Unlicense; https://github.com/yt-dlp/yt-dlp |
| Glide | 4.16.0 | BSD / Apache-2.0 and bundled notices; https://github.com/bumptech/glide |
| Google Play services Auth | 21.6.0 | Google Play services SDK terms; https://developers.google.com/android/guides/overview |

Gradle/AGP are build tools. Transitive libraries (including Kotlin, Guava,
AndroidX and native Python libraries) retain their respective upstream licenses.
The Gradle dependency report identifies the complete runtime dependency tree:
`./gradlew :app:dependencies --configuration debugRuntimeClasspath`.

Offline copies of the main open-source license texts are packaged in
`app/src/main/assets/licenses/`. Google Play services runs under Google's SDK
terms; the APK does not contain a desktop OAuth secret, user token, signing key,
or the publisher's desktop configuration file.
