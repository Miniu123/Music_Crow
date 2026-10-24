"""Create an auditable, self-contained Flatpak build directory from this checkout."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('output', type=Path)
parser.add_argument('--with-google-client', action='store_true', help='Bundle publisher Desktop OAuth configuration, never user tokens')
args = parser.parse_args()
recipe = Path(__file__).resolve().parent
project = recipe.parent.parent
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
app_id = 'io.github.Miniu123.MusicCrow'
version = '0.1.0'
app = out / 'app-source'
app.mkdir(exist_ok=True)
for folder in ('core', 'ui'):
    (app / folder).mkdir(exist_ok=True)
    for source in (project / folder).glob('*.py'):
        shutil.copy2(source, app / folder / source.name)
for name in ('main.py', 'README.md', 'requirements.txt', 'LICENSE', 'THIRD_PARTY_NOTICES.md'):
    shutil.copy2(project / name, app / name)
shutil.copytree(project / 'assets', app / 'assets', dirs_exist_ok=True)
if not args.with_google_client and (app / 'core/google_oauth_client.json').exists():
    raise SystemExit('This output already contains OAuth configuration; choose a fresh output directory.')
if args.with_google_client:
    source = project / 'core/google_oauth_client.json'
    data = json.loads(source.read_text())
    assert 'installed' in data and 'token' not in data and 'refresh_token' not in data
    shutil.copy2(source, app / 'core/google_oauth_client.json')
    (app / 'core/google_oauth_client.json').chmod(0o600)
shutil.copytree(recipe / 'sources', out / 'sources', dirs_exist_ok=True)
shutil.copytree(recipe / 'wheels', out / 'wheels', dirs_exist_ok=True)
lock = json.loads((out / 'sources/sources.lock.json').read_text())
def archive(name):
    return {'type': 'archive', 'path': 'sources/' + name, 'sha256': lock[name]['sha256']}

(out / 'lua.pc').write_text('''prefix=/app
libdir=${prefix}/lib
includedir=${prefix}/include/lua5.2
Name: Lua
Description: Lua 5.2
Version: 5.2.4
Libs: -L${libdir} -llua -lm -ldl
Cflags: -I${includedir}
''')
(out / 'music-crow').write_text('''#!/bin/sh
export PYTHONPATH=/app/lib/python3.13/site-packages:/app/share/music-crow
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1
export LC_NUMERIC=C
exec python3 /app/share/music-crow/main.py "$@"
''')
(out / (app_id + '.desktop')).write_text(f'''[Desktop Entry]
Type=Application
Name=Music Crow
Comment=Discover music and build your own listening queue
Comment[pl]=Odkrywaj muzykę i układaj własną kolejkę
Exec=music-crow
Icon={app_id}
Terminal=false
Categories=AudioVideo;Audio;Player;
StartupNotify=true
StartupWMClass={app_id}
''')
(out / (app_id + '.metainfo.xml')).write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>{app_id}</id>
  <name>Music Crow</name>
  <summary>Discover music and organise your listening queue</summary>
  <metadata_license>CC0-1.0</metadata_license>
  <developer id="io.github.Miniu123"><name>Miniu123</name></developer>
  <description><p>A desktop music player with playlists, personalised recommendations and optional Google Drive backups.</p></description>
  <launchable type="desktop-id">{app_id}.desktop</launchable>
  <url type="homepage">https://miniu123.github.io/Music_Crow/</url>
  <url type="bugtracker">https://github.com/Miniu123/Music_Crow/issues</url>
  <releases><release version="{version}" date="2026-10-21"/></releases>
  <content_rating type="oars-1.1"/>
</component>
''')
wheels = [{'type': 'file', 'path': 'wheels/' + p.name, 'dest': 'wheels',
           'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((out / 'wheels').glob('*.whl'))]
manifest = {
 'app-id': app_id, 'runtime': 'org.freedesktop.Platform', 'runtime-version': '25.08',
 'sdk': 'org.freedesktop.Sdk', 'command': 'music-crow', 'default-branch': 'stable',
 'finish-args': ['--share=network', '--share=ipc', '--socket=wayland', '--socket=fallback-x11',
                 '--socket=pulseaudio', '--device=dri', '--own-name=org.mpris.MediaPlayer2.musiccrow',
                 '--env=PYTHONPATH=/app/lib/python3.13/site-packages:/app/share/music-crow'],
 'build-options': {'strip': True, 'env': {'PYTHONPATH': '/app/lib/python3.13/site-packages'}},
 'modules': [
  {'name': 'lua', 'buildsystem': 'simple', 'build-commands': [
    'make -C src linux MYCFLAGS=-fPIC',
    'install -Dm644 src/liblua.a /app/lib/liblua.a',
    'mkdir -p /app/include/lua5.2 && install -m644 src/lua.h src/luaconf.h src/lauxlib.h src/lualib.h /app/include/lua5.2/',
    'install -Dm644 lua.pc /app/lib/pkgconfig/lua5.2.pc'],
   'sources': [archive('lua-5.2.4.tar.gz'), {'type': 'file', 'path': 'lua.pc'}]},
  {'name': 'libass', 'config-opts': ['--disable-static'], 'sources': [archive('libass-0.17.4.tar.gz')]},
  {'name': 'libplacebo', 'buildsystem': 'meson',
   'config-opts': ['-Dauto_features=disabled', '-Ddemos=false'],
   'sources': [archive('libplacebo-v7.349.0.tar.gz')]},
  {'name': 'mpv', 'buildsystem': 'meson',
   'config-opts': ['-Dauto_features=disabled', '-Dlibmpv=true', '-Dcplayer=false',
                   '-Dlua=lua5.2', '-Dpulse=enabled', '-Dgl=disabled', '-Dbuild-date=false'],
   'sources': [archive('mpv-v0.40.0.tar.gz')]},
  {'name': 'deno', 'buildsystem': 'simple', 'build-commands': ['install -Dm755 deno /app/bin/deno'],
   'sources': [dict(archive('deno-x86_64.zip'), **{'archive-type': 'zip', 'strip-components': 0})]},
  {'name': 'dbus-python', 'buildsystem': 'meson',
   'config-opts': ['-Dtests=false'], 'sources': [archive('dbus-python-1.4.0.tar.gz')]},
  {'name': 'pygobject', 'buildsystem': 'meson',
   'config-opts': ['-Dpycairo=disabled', '-Dtests=false'], 'sources': [archive('pygobject-3.52.3.tar.gz')]},
  {'name': 'python-dependencies', 'buildsystem': 'simple',
   'build-commands': ['pip3 install --no-index --no-deps --no-compile --prefix=/app wheels/*.whl'], 'sources': wheels},
  {'name': 'krb5', 'subdir': 'src', 'config-opts': ['--disable-static', '--without-system-verto', '--without-ldap'],
   'sources': [archive('krb5-1.22.2.tar.gz')],
   'cleanup': ['/bin', '/sbin', '/share/man', '/share/doc']},
  {'name': 'music-crow', 'buildsystem': 'simple', 'build-commands': [
    # The application supports Polish and English. Keep native Qt dialogs in
    # those languages without shipping unused translations in the bundle.
    "find /app/lib/python3.13/site-packages/PyQt6/Qt6/translations -type f -name '*.qm' ! -name '*_pl.qm' ! -name '*_en.qm' -delete",
    'mkdir -p /app/share/music-crow && cp -a app-source/. /app/share/music-crow/',
    'install -Dm755 music-crow /app/bin/music-crow',
    f'install -Dm644 {app_id}.desktop /app/share/applications/{app_id}.desktop',
    f'install -Dm644 {app_id}.metainfo.xml /app/share/metainfo/{app_id}.metainfo.xml',
    f'install -Dm644 app-source/assets/icon.png /app/share/icons/hicolor/256x256/apps/{app_id}.png'],
   'sources': [{'type':'dir','path':'app-source','dest':'app-source'}] +
              [{'type':'file','path':n} for n in ('music-crow',app_id+'.desktop',app_id+'.metainfo.xml')]}
 ],
 'cleanup': ['/include', '/lib/pkgconfig', '*.a', '*.la']
}
manifest['modules'].sort(key=lambda module: module['name'] != 'python-dependencies')
(out / (app_id + '.json')).write_text(json.dumps(manifest, indent=2) + '\n')
(out / 'build.sh').write_text(f'''#!/bin/sh
set -eu
cd "$(dirname "$0")"
flatpak run org.flatpak.Builder --user --force-clean --disable-rofiles-fuse --repo=repo build-dir {app_id}.json
flatpak build-bundle repo Music-Crow-{version}-x86_64.flatpak {app_id} stable --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo
sha256sum Music-Crow-{version}-x86_64.flatpak > SHA256SUMS
''')
(out / 'build.sh').chmod(0o755)
print('Prepared',out)
print('Desktop Google client included:',args.with_google_client)
print('User tokens and private library are excluded by the source allowlist.')
