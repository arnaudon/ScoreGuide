"""Tests for file_helper.py (local storage logic, S3 mocked)."""

import io
import os
from pathlib import Path

import pytest

from app.file_helper import file_helper


@pytest.fixture(autouse=True)
def set_data_path_tmp(tmp_path, monkeypatch):
    """Set DATA_PATH env var to tmp_path."""
    monkeypatch.setenv("DATA_PATH", str(tmp_path))


def test_upload_and_download_and_delete_local(monkeypatch):
    """Test local file upload, download and delete."""
    # Ensure we're not using S3
    monkeypatch.setenv("S3_ENDPOINT", "")
    monkeypatch.setenv("S3_BUCKET", "")
    file_content = b"test pdf content"
    filename = "testfile.pdf"
    fileobj = io.BytesIO(file_content)

    # Upload (should store locally)
    file_helper.upload_pdf(filename, fileobj)
    written_file = Path(os.getenv("DATA_PATH")) / filename
    assert written_file.exists()

    # Download
    out = file_helper.download_pdf(filename)
    assert out["Body"].read() == file_content
    out["Body"].close()

    # Delete
    file_helper.delete_pdf(filename)
    assert not written_file.exists()


def test_get_size_and_download_range_local(monkeypatch):
    """Test local get_size and a ranged download, used for PDF Range requests."""
    monkeypatch.setenv("S3_ENDPOINT", "")
    monkeypatch.setenv("S3_BUCKET", "")
    file_content = b"0123456789abcdef"
    filename = "ranged.pdf"
    file_helper.upload_pdf(filename, io.BytesIO(file_content))

    assert file_helper.get_size(filename) == len(file_content)

    out = file_helper.download_pdf(filename, byte_range=(2, 5))
    assert b"".join(out["Body"]) == file_content[2:6]

    file_helper.delete_pdf(filename)


def test_upload_and_delete_local_handles_missing_file(monkeypatch):
    """Test deleting missing local file handles exception silently."""
    # This test ensures no exception raised if deleting a non-existent local file
    monkeypatch.setenv("S3_ENDPOINT", "")
    monkeypatch.setenv("S3_BUCKET", "")
    file_helper.delete_pdf("does_not_exist.pdf")


@pytest.mark.parametrize("filename", ["../escape.pdf", "../../etc/passwd", "/etc/passwd", ""])
def test_local_path_rejects_traversal(monkeypatch, filename):
    """Filenames escaping DATA_PATH are rejected in all local operations."""
    monkeypatch.setenv("S3_ENDPOINT", "")
    monkeypatch.setenv("S3_BUCKET", "")
    with pytest.raises(ValueError):
        file_helper.upload_pdf(filename, io.BytesIO(b"x"))
    with pytest.raises(ValueError):
        file_helper.download_pdf(filename)
    with pytest.raises(ValueError):
        file_helper.get_size(filename)
    with pytest.raises(ValueError):
        file_helper.delete_pdf(filename)
