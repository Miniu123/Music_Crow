"""Load the publisher's Desktop OAuth client from an untracked release file.

The publisher supplies core/google_oauth_client.json when packaging a release.
End users sign in through their system browser without importing a file.
Never include user tokens, service-account keys, or web client credentials.
See README.md -> Publisher setup for Google sign-in.
"""

import json
from pathlib import Path


CLIENT_CONFIG_PATH = Path(__file__).with_name('google_oauth_client.json')


def bundled_client():
    try:
        content = CLIENT_CONFIG_PATH.read_text(encoding='utf-8')
    except OSError:
        return None
    # The caller validates the Desktop client type and trusted Google endpoints.
    return json.loads(content)
