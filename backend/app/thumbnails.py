"""Small first-page images of score PDFs, shown on the library's cards.

One image per stored PDF (``thumbnails/<pdf stem>.png``): scores sharing a PDF
share it. It is made by the table-of-contents job, which has the PDF in hand
already, and by ``python -m app.thumbnails backfill`` for older PDFs; it goes
with its PDF (``uploads._delete_file``).
"""

import argparse
import io
import logging
from pathlib import PurePosixPath
from typing import Annotated

import pypdfium2 as pdfium
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.db import get_session
from app.file_helper import file_helper
from app.users import get_current_user
from shared.scores import Score
from shared.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

# Rendered width in pixels: a card shows it at ~80 CSS px, so this is sharp on
# high-density screens and stays around 10-30 kB.
THUMB_WIDTH = 240
# A page taller than this many widths (a scroll, a broken PDF) is cut.
MAX_ASPECT = 2.0


def thumbnail_name(pdf_path: str) -> str:
    """Where a PDF's thumbnail is stored."""
    return f"thumbnails/{PurePosixPath(pdf_path).stem}.png"


def render(data: bytes) -> bytes | None:
    """The PDF's first page as a small grayscale PNG, or None if it can't be read."""
    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError:
        return None
    try:
        if len(pdf) == 0:
            return None
        page = pdf[0]
        width, height = page.get_size()
        if width <= 0 or height <= 0:
            return None
        image = page.render(scale=THUMB_WIDTH / width, grayscale=True).to_pil()
        image = image.crop((0, 0, image.width, min(image.height, int(image.width * MAX_ASPECT))))
        buf = io.BytesIO()
        image.convert("L").save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    finally:
        pdf.close()


def store(pdf_path: str, data: bytes) -> bool:
    """Render and store the thumbnail of ``pdf_path`` (its bytes in ``data``)."""
    png = render(data)
    if png is None:
        return False
    file_helper.upload_file(thumbnail_name(pdf_path), io.BytesIO(png), "image/png")
    return True


def store_safely(pdf_path: str, data: bytes) -> None:
    """``store``, logging instead of failing: a missing thumbnail only shows a placeholder."""
    try:
        store(pdf_path, data)
    except Exception:  # pragma: no cover - storage hiccup
        logger.exception("could not store the thumbnail of %s", pdf_path)


def delete(pdf_path: str) -> None:
    """Remove a PDF's thumbnail (no error if there is none)."""
    file_helper.delete_pdf(thumbnail_name(pdf_path))


def _exists(name: str) -> bool:
    try:
        file_helper.get_size(name)
    except Exception:
        return False
    return True


def backfill(session: Session) -> int:
    """Make the thumbnails missing for stored PDFs, one at a time; returns how many."""
    made = 0
    paths = session.exec(select(Score.pdf_path).where(Score.pdf_path != "").distinct()).all()
    for pdf_path in paths:
        if _exists(thumbnail_name(pdf_path)):
            continue
        try:
            data = file_helper.download_pdf(pdf_path)["Body"].read()
        except Exception:
            logger.warning("backfill: cannot read %s", pdf_path)
            continue
        if store(pdf_path, data):
            made += 1
    return made


@router.get("/scores/{score_id}/thumbnail")
def get_thumbnail(
    score_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Stream the score's first-page image (404 until it has been made)."""
    score = session.exec(
        select(Score).where(Score.id == score_id, Score.user_id == current_user.id)
    ).first()
    if score is None or not score.pdf_path:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    try:
        obj = file_helper.download_pdf(thumbnail_name(score.pdf_path))
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail="Thumbnail not found") from e
    except Exception as e:  # pragma: no cover - S3: NoSuchKey
        raise HTTPException(status_code=404, detail="Thumbnail not found") from e
    return StreamingResponse(
        obj["Body"],
        media_type="image/png",
        # Keyed by the PDF: a score given another PDF gets another image, but the
        # URL stays /scores/<id>/thumbnail, so keep the cache short.
        headers={"Cache-Control": "private, max-age=3600"},
    )


def main() -> None:  # pragma: no cover - deploy entry point
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["backfill"])
    parser.parse_args()
    from app.db import engine

    logging.basicConfig(level=logging.INFO)
    with Session(engine) as session:
        logger.info("thumbnails made: %d", backfill(session))


if __name__ == "__main__":  # pragma: no cover
    main()
