import base64

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.config import ConfigError, Settings


def test_push_config_requires_matching_keys_and_private_value_is_redacted():
    key = ec.generate_private_key(ec.SECP256R1())
    private = base64.urlsafe_b64encode(key.private_numbers().private_value.to_bytes(32, "big")).decode().rstrip("=")
    public = base64.urlsafe_b64encode(key.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint)).decode().rstrip("=")
    settings = Settings(push_enabled=True, push_private_key=private, push_public_key=public,
                        push_professor_email="professor@example.com", push_contact_email="operator@example.com")
    settings.validate()
    assert private not in repr(settings)
    settings.push_private_key = "invalid"
    with pytest.raises(ConfigError):
        settings.validate()
    settings.push_private_key = private
    settings.push_contact_email = "bad\r\nvalue"
    with pytest.raises(ConfigError):
        settings.validate()


def test_push_disabled_needs_no_secret():
    Settings().validate()
