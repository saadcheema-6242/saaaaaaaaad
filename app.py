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

    raw = (mrz.aux or {}).get("text", "") if hasattr(mrz, "aux") else ""
    lines = [ln for ln in raw.replace("\r", "").split("\n") if ln.strip()]

    if len(lines) >= 2 and len(lines[-1].strip()) >= 40:
        result = parse_td3(lines[-2], lines[-1])
    else:
        raise HTTPException(422, "MRZ was found but could not be read as a passport (TD3). Try a clearer photo.")

    return result
