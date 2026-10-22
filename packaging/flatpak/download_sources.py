"""Fetch upstream sources; subsequent builds use the manifest's SHA-256 pins."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

root = Path(__file__).resolve().parent / 'sources'
root.mkdir(exist_ok=True)
sources = {
    'krb5-1.22.2.tar.gz': 'https://web.mit.edu/kerberos/dist/krb5/1.22/krb5-1.22.2.tar.gz',
    'lua-5.2.4.tar.gz': 'https://www.lua.org/ftp/lua-5.2.4.tar.gz',
    'libass-0.17.4.tar.gz': 'https://codeload.github.com/libass/libass/tar.gz/refs/tags/0.17.4',
    'libplacebo-v7.349.0.tar.gz': 'https://codeload.github.com/haasn/libplacebo/tar.gz/refs/tags/v7.349.0',
    'mpv-v0.40.0.tar.gz': 'https://codeload.github.com/mpv-player/mpv/tar.gz/refs/tags/v0.40.0',
    'deno-x86_64.zip': 'https://github.com/denoland/deno/releases/download/v2.9.5/deno-x86_64-unknown-linux-gnu.zip',
}
for package, version, filename in [('dbus-python', '1.4.0', 'dbus-python-1.4.0.tar.gz'),
                                   ('PyGObject', '3.52.3', 'pygobject-3.52.3.tar.gz')]:
    with urlopen(f'https://pypi.org/pypi/{package}/{version}/json', timeout=30) as response:
        info = json.load(response)
    release = next(item for item in info['urls'] if item['packagetype'] == 'sdist')
    sources[filename] = release['url']
lock = {}
for name, url in sources.items():
    path = root / name
    if not path.exists():
        with urlopen(url, timeout=120) as response:
            data = response.read()
        path.write_bytes(data)
    lock[name] = {'url': url, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    print(name, path.stat().st_size)
(root / 'sources.lock.json').write_text(json.dumps(lock, indent=2) + '\n')
