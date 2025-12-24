import os
from io import BytesIO

from flask import Flask, abort, render_template_string, request, send_file
from werkzeug.utils import secure_filename

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, ContentStream, NameObject

from unredact import _remove_black_rectangles, _remove_redaction_annots

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Unredact.net</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=Playfair+Display:wght@600&display=swap"
      rel="stylesheet"
    />
    <style>
      :root {
        --bg: #f5f1e9;
        --ink: #1e1b16;
        --accent: #c94f24;
        --panel: #ffffff;
      }
      body {
        margin: 0;
        font-family: "IBM Plex Sans", system-ui, -apple-system, sans-serif;
        background: radial-gradient(circle at top, #fff3dd, var(--bg));
        color: var(--ink);
      }
      main {
        max-width: 720px;
        margin: 2vh auto 4vh;
        padding: 16px;
      }
      .card {
        background: var(--panel);
        border: 2px solid var(--ink);
        padding: 24px;
        box-shadow: 10px 12px 0 #00000020;
      }
      .logo {
        display: block;
        width: clamp(220px, 50vw, 512px);
        max-width: 100%;
        height: auto;
        margin: 0 auto 16px;
      }
      p {
        margin: 0 0 20px;
        line-height: 1.5;
      }
      form {
        display: grid;
        gap: 14px;
      }
      input[type="file"] {
        border: 2px dashed var(--ink);
        padding: 16px;
        background: #fff9ef;
      }
      button {
        background: var(--accent);
        border: none;
        padding: 12px 16px;
        font-size: 1rem;
        color: #fff;
        cursor: pointer;
      }
      button:hover {
        filter: brightness(0.95);
      }
      .note {
        font-size: 0.9rem;
        color: #4a3e35;
      }
      @media (max-width: 640px) {
        main {
          margin: 1vh auto 3vh;
          padding: 12px;
        }
        .card {
          padding: 18px;
        }
      }
    </style>
  </head>
  <body>
    <main>
      <div class="card">
        <img class="logo" src="/static/unredact.jpg" alt="Unredact.net logo" />
        <p>Upload a PDF with redaction overlays, and get a cleaned version back.</p>
        <form method="post" enctype="multipart/form-data">
          <input type="file" name="pdf" accept="application/pdf" required />
          <button type="submit">Unredact PDF</button>
        </form>
        <p class="note">This only removes overlay marks; it cannot recover content that was permanently removed.</p>
        <p class="note">
          Built by <a href="https://linkedin.com/in/drvink" target="_blank" rel="noopener">Dennis Vink</a>.
          <a href="https://github.com/dennisvink/unredact" target="_blank" rel="noopener">GitHub repo</a>.
        </p>
      </div>
    </main>
  </body>
</html>
"""


def _unredact_pdf(data: bytes) -> BytesIO:
    reader = PdfReader(BytesIO(data))
    writer = PdfWriter()

    for page in reader.pages:
        _remove_redaction_annots(page, aggressive=True)
        _remove_black_rectangles(page, reader, aggressive=True)
        writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    output.seek(0)
    return output


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template_string(HTML)

    uploaded = request.files.get("pdf")
    if not uploaded or not uploaded.filename:
        abort(400, "Missing PDF upload")

    filename = secure_filename(uploaded.filename)
    base, _ext = os.path.splitext(filename)
    output_name = f"{base or 'unredacted'}_unredacted.pdf"

    data = uploaded.read()
    if not data:
        abort(400, "Uploaded file is empty")

    output = _unredact_pdf(data)
    return send_file(
        output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=output_name,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
