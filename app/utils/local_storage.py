import asyncio
import base64
import os
from pathlib import Path

import fitz

LOCAL_STORAGE_DIR = Path(os.environ.get("LOCAL_STORAGE_DIR", "/data/pdfs"))
DEFAULT_DPI = 150


def _write_file_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)  # atomic rename, so readers never see a half-written file


def pdf_path(hash_: str) -> Path:
    return LOCAL_STORAGE_DIR / "pdfs" / f"{hash_}.pdf"


async def save_pdf_to_volume(pdf_bytes: bytes, hash_: str) -> dict:
    path = pdf_path(hash_)
    if not path.exists():  # content-addressed: same hash = same file
        await asyncio.to_thread(_write_file_atomic, path, pdf_bytes)
    return {"url": f"file://{path}", "key": f"pdfs/{hash_}.pdf", "path": str(path), "storage": "local"}


async def load_pdf_bytes_from_volume(hash_: str) -> bytes:
    path = pdf_path(hash_)
    if not path.exists():
        raise FileNotFoundError(path)
    return await asyncio.to_thread(path.read_bytes)


def _render_pages(pdf_bytes: bytes, hash_: str, pages: list, dpi: int | None) -> dict[str, str]:
    dpi = dpi or DEFAULT_DPI
    out = {}
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in pages:
            idx = int(page) - 1  # pages are 1-based, same as upload_pdf
            if not 0 <= idx < doc.page_count:
                raise ValueError(f"Page {page} out of range (document has {doc.page_count} pages).")
            path = LOCAL_STORAGE_DIR / hash_ / "pages" / f"{page}_{dpi}.png"
            if not path.exists():  # reuse earlier renders at the same dpi
                pix = doc[idx].get_pixmap(dpi=dpi)
                _write_file_atomic(path, pix.tobytes("png"))
            out[str(page)] = str(path)
    return out


async def render_pages_to_volume(pdf_bytes: bytes, hash_: str, pages: list, dpi: int | None) -> dict[str, str]:
    """Render pages to PNGs on the volume. Returns {page: file path}."""
    return await asyncio.to_thread(_render_pages, pdf_bytes, hash_, pages, dpi)


def image_data_url(path: str) -> str:
    """Inline the image so the LLM provider doesn't have to fetch it."""
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()