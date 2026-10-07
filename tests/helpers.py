import os
import tempfile
import threading

os.environ.setdefault("ACCSOFT_DATA", tempfile.mkdtemp(prefix="accsoft-test-"))

from accsoft import ed25519, pubkey  # noqa: E402
from accsoft.db import DB  # noqa: E402

TEST_SEED = bytes(range(32))
pubkey.PUBLIC_KEY_HEX = ed25519.publickey(TEST_SEED).hex()


def fresh_db():
    return DB(":memory:")
