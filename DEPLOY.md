# Deploying the Passport MRZ Scanner (free public URL)

The app needs the **Tesseract** OCR engine, so it's shipped as a Docker image
(`Dockerfile`). Any host that builds Dockerfiles will work. Below is the
fastest free path (**Render**), plus a **Hugging Face Spaces** alternative.

All deployment files live on the **`saad`** branch:
- `Dockerfile` — installs Tesseract + the app, runs uvicorn on `$PORT`
- `render.yaml` — Render Blueprint (pre-fills the service config)
- `.dockerignore` — keeps the image small

---

## Option 1 — Render (recommended, ~5 min)

1. Go to <https://render.com> and **Sign up / Log in with GitHub** (free, no card).
2. Click **New +** → **Web Service**.
3. **Connect** this repository (`saadcheema-6242/saaaaaaaaad`). If Render asks,
   grant it access to the repo.
4. Select the **`saad`** branch. Render auto-detects the `Dockerfile`
   (Language = Docker). Leave the rest at defaults; pick the **Free** plan.
5. Click **Create Web Service**. First build takes a few minutes (it installs
   Tesseract + Python deps).
6. When it goes **Live**, your public URL is shown at the top, e.g.
   `https://passport-mrz-scanner.onrender.com` — open it and test.

> Free Render services sleep after ~15 min idle; the first request after that
> takes ~50s to wake, then it's fast.

---

## Option 2 — Hugging Face Spaces (free, no card)

1. Go to <https://huggingface.co> and create a free account.
2. **New** → **Space**. Choose **Docker** → **Blank**. Name it, set visibility
   to Public, create it.
3. In the Space's **Files**, upload the repo contents from the `saad` branch
   (at least: `Dockerfile`, `app.py`, `mrz_utils.py`, `requirements.txt`,
   `static/`), **or** link the GitHub repo.
4. Add this front matter to the top of the Space's `README.md` so it exposes
   the right port:
   ```
   ---
   title: Passport MRZ Scanner
   emoji: 🛂
   sdk: docker
   app_port: 8000
   ---
   ```
5. The Space builds automatically; when it's running, the public URL is
   `https://<your-username>-<space-name>.hf.space`.

---

## Testing it

Open the URL, then either drag in / upload a passport **photo page** (the two
`<<<<`-filled MRZ lines at the bottom must be clearly visible, flat and well
lit) or use the **webcam** button. The result shows every parsed field and a
green/red badge per check digit.

No passport handy? Any clear image of a TD3 MRZ works — including a printout of
the ICAO specimen lines:
```
P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<
L898902C36UTO7408122F1204159ZE184226B<<<<<10
```

## Run locally (optional)

```bash
docker build -t passport-scanner .
docker run --rm -p 8000:8000 passport-scanner
# open http://localhost:8000
```
