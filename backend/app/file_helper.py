"""File helper to handle both local and S3 bucket."""

import contextlib
import os
import shutil
from pathlib import Path

import boto3
from botocore.config import Config


class FileHelper:
    """File helper, S3 of local."""

    def __init__(self):
        """Initialize the S3 helper."""
        self.endpoint = os.getenv("S3_ENDPOINT")
        self.bucket = os.getenv("S3_BUCKET")
        self.s3_client = self._init_s3_client() if self.endpoint is not None else None

    def _init_s3_client(self):  # pragma: no cover
        """Initialize the S3 client."""
        return boto3.client(
            "s3",
            endpoint_url="https://" + str(self.endpoint),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
            region_name=os.getenv("S3_REGION", "us-east-1"),
            config=Config(
                signature_version="s3v4",
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )

    @staticmethod
    def _local_path(filename) -> Path:
        """Resolve filename under DATA_PATH, rejecting path traversal."""
        base = Path(str(os.getenv("DATA_PATH"))).resolve()
        path = (base / filename).resolve()
        if path == base or not path.is_relative_to(base):
            raise ValueError(f"invalid filename: {filename!r}")
        return path

    def upload_pdf(self, filename, file):
        """Upload a pdf file."""
        if self.s3_client:  # pragma: no cover
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=filename,
                Body=file,
                ContentType="application/pdf",
                ContentDisposition="inline",
            )
        else:
            path = self._local_path(filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                shutil.copyfileobj(file, f)

    def delete_pdf(self, filename):
        """Delete a pdf file."""
        if self.s3_client:  # pragma: no cover
            self.s3_client.delete_object(Bucket=self.bucket, Key=filename)
        else:
            with contextlib.suppress(FileNotFoundError):
                os.remove(self._local_path(filename))

    def get_size(self, filename) -> int:
        """Return the size in bytes of a stored pdf, for building Range responses."""
        if self.s3_client:  # pragma: no cover
            return self.s3_client.head_object(Bucket=self.bucket, Key=filename)["ContentLength"]
        return self._local_path(filename).stat().st_size

    def download_pdf(self, filename, byte_range: tuple[int, int] | None = None):
        """Download a pdf file, optionally only the ``(start, end)`` inclusive byte range.

        Range support lets PDF.js fetch and prerender only the pages it needs
        instead of downloading the whole file before it can show anything.
        """
        if self.s3_client:  # pragma: no cover
            kwargs = {"Bucket": self.bucket, "Key": filename}
            if byte_range is not None:
                start, end = byte_range
                kwargs["Range"] = f"bytes={start}-{end}"
            return self.s3_client.get_object(**kwargs)

        # Deliberately outlives this function — StreamingResponse reads and
        # closes it (or _bounded_reader does, below), not a `with` block here.
        f = open(self._local_path(filename), "rb")  # noqa: SIM115
        if byte_range is None:
            return {"Body": f}
        start, end = byte_range
        f.seek(start)
        return {"Body": _bounded_reader(f, end - start + 1)}


def _bounded_reader(f, length: int, chunk_size: int = 64 * 1024):
    """Yield at most ``length`` bytes from an open file handle, then close it."""
    remaining = length
    try:
        while remaining > 0:
            chunk = f.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
    finally:
        f.close()


file_helper = FileHelper()
