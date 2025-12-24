# Unredact.net

Minimal Flask app that removes PDF redaction overlays using `pypdf`. Upload a PDF and receive an unredacted copy back.

# Demo

https://unredact.net

## Build

```bash
docker build -t unredact .
```

## Run locally

```bash
docker run -p 8080:8080 unredact
```

Then open `http://localhost:8080`.

## Deploy to Cloud Run

```bash
gcloud run deploy unredact \
  --source . \
  --region YOUR_REGION \
  --allow-unauthenticated
```

Optional: set a specific service name or port via `--service` and `--port`.
