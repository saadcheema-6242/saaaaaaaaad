# Passport MRZ Scanner

FastAPI backend + plain HTML frontend. Reads the machine readable zone (MRZ) of a passport photo page, parses it (ICAO 9303, TD3) and verifies every check digit.

## Setup

1. Install Tesseract OCR (PassportEye needs it):
   - Windows: https://github.com/UB-Mannheim/tesseract/wiki (add it to PATH)
   - Ubuntu/Debian: `sudo apt install tesseract-ocr`
   - macOS: `brew install tesseract`
2. Install Python packages:
   ```
   pip install -r requirements.txt
   ```
3. Run:
   ```
   uvicorn app:app --reload
   ```
4. Open http://localhost:8000

The webcam button needs HTTPS or localhost. On a phone, the file picker opens the camera directly.

## API

`POST /api/scan` with multipart field `file` (JPG, PNG, WEBP, BMP, TIFF, max 10 MB). Returns JSON:

```json
{
  "surname": "ERIKSSON", "given_names": "ANNA MARIA",
  "passport_number": "L898902C3", "nationality": "UTO",
  "date_of_birth": "1974-08-12", "sex": "F", "expiry_date": "2012-04-15",
  "checks": {"passport_number": true, "date_of_birth": true, "expiry_date": true,
             "personal_number": true, "composite": true},
  "valid": true
}
```

If `valid` is false, ask the user to rescan instead of trusting the data.

## Files

- `app.py`: FastAPI routes, image handling (temp file is deleted right after OCR)
- `mrz_utils.py`: TD3 parser, check digits, OCR digit/letter correction
- `static/index.html`: upload, drag and drop, webcam capture, result view

## Next steps

- Add a crop/deskew step (OpenCV) if photos come in at bad angles.
- Fine-tune only if real samples keep failing the check digits.
- Support TD1 (ID cards, 3 lines of 30) if needed.
- Passport images are sensitive: serve over HTTPS, do not log or store them.
