import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from mrz_utils import parse_td3

try:
    from passporteye import read_mrz
except ImportError:  # lets the server start so you can see a clear error
    read_mrz = None

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED = {"image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"}
BASE = Path(__file__).parent


def _looks_like_image(data: bytes) -> bool:
    """Validate the actual bytes, not the client-supplied content type."""
    if data[:3] == b"\xff\xd8\xff":                      # JPEG
        return True
    if data[:8] == b"\x89PNG\r\n\x1a\n":                  # PNG
        return True
    if data[:2] == b"BM":                                # BMP
        return True
    if data[:4] in (b"II*\x00", b"MM\x00*"):             # TIFF (LE / BE)
        return True
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":    # WEBP
        return True
    return False


def _raw_mrz_text(mrz) -> str:
    """Pull the OCR'd MRZ text out of a PassportEye result.

    PassportEye exposes it a few different ways across versions; try the
    richest source first and fall back, so a changed/empty ``aux`` key does
    not silently turn every scan into a "no MRZ found" error.
    """
    aux = getattr(mrz, "aux", None) or {}
    text = (aux.get("text") or "").strip()
    if text:
        return text
    try:
        return (mrz.to_dict().get("raw_text") or "").strip()
    except Exception:
        return ""

app = FastAPI(title="Passport MRZ Scanner")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(BASE / "static" / "index.html")


@app.post("/api/scan")
async def scan(file: UploadFile = File(...)):
    if read_mrz is None:
        raise HTTPException(500, "PassportEye is not installed. Run: pip install -r requirements.txt")
    if file.content_type not in ALLOWED:
        raise HTTPException(415, "Please upload a JPG, PNG, WEBP, BMP or TIFF image.")

    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Image is larger than 10 MB.")
    if not _looks_like_image(data):
        raise HTTPException(415, "That file is not a JPG, PNG, WEBP, BMP or TIFF image.")

    # Privacy: the image only exists on disk while it is being processed.
    suffix = Path(file.filename or "scan.jpg").suffix or ".jpg"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        mrz = read_mrz(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    if mrz is None:
        raise HTTPException(422, "No MRZ found. Retake the photo: flat, well lit, whole photo page in frame.")

    raw = _raw_mrz_text(mrz)
    lines = [ln for ln in raw.replace("\r", "").split("\n") if ln.strip()]

    if len(lines) >= 2 and len(lines[-1].strip()) >= 40:
        result = parse_td3(lines[-2], lines[-1])
    else:
        raise HTTPException(422, "MRZ was found but could not be read as a passport (TD3). Try a clearer photo.")

    return result
