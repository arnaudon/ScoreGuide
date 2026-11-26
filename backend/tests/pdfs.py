"""Small real PDFs for upload tests (uploads must open in pdfium)."""

import io

import pypdfium2 as pdfium


def make_pdf(pages: int = 1, size: tuple[float, float] = (595, 842)) -> bytes:
    """A valid PDF with ``pages`` blank pages of ``size`` points."""
    pdf = pdfium.PdfDocument.new()
    for _ in range(pages):
        pdf.new_page(*size)
    buf = io.BytesIO()
    pdf.save(buf)
    pdf.close()
    return buf.getvalue()


PDF = make_pdf()
