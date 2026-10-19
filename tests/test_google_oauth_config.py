import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import google_oauth_config as config


class PublisherConfigurationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'google_oauth_client.json'
        replacement = patch.object(config, 'CLIENT_CONFIG_PATH', self.path)
        replacement.start()
        self.addCleanup(replacement.stop)

    def test_source_checkout_without_release_file_has_no_client(self):
        self.assertIsNone(config.bundled_client())

    def test_release_configuration_is_loaded_independent_of_working_directory(self):
        client = {'installed': {'client_id': 'test-client', 'client_secret': 'test-value'}}
        self.path.write_text(json.dumps(client), encoding='utf-8')
        self.assertEqual(config.bundled_client(), client)

    def test_malformed_release_configuration_is_rejected(self):
        self.path.write_text('{invalid', encoding='utf-8')
        with self.assertRaises(ValueError):
            config.bundled_client()

    def test_unreadable_file_disables_bundled_configuration(self):
        with patch.object(Path, 'read_text', side_effect=PermissionError):
            self.assertIsNone(config.bundled_client())


if __name__ == '__main__':
    unittest.main()
