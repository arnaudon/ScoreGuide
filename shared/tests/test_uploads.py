"""Tests for the upload model."""

from shared.uploads import Upload
from shared.usage import utcnow


def test_upload_defaults():
    row = Upload(user_id=1, filename="a.pdf")
    assert row.size == 0
    assert abs((utcnow() - row.created_at).total_seconds()) < 5
