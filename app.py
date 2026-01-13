from flask import Flask, render_template, request, send_file, redirect, url_for
from pathlib import Path
from PIL import Image
import io

app = Flask(__name__)


def centre_crop_to_square(img: Image.Image) -> Image.Image:
    width, height = img.size
    if width == height:
        return img
    new_size = min(width, height)
    left = (width - new_size) // 2
    top = (height - new_size) // 2
    right = left + new_size
    bottom = top + new_size
    return img.crop((left, top, right, bottom))


def resize_for_routenote(input_image: Image.Image) -> bytes:
    img = input_image.convert("RGB")
    square = centre_crop_to_square(img)
    resized = square.resize((3000, 3000), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    resized.save(buffer, format="JPEG", quality=95, optimize=True, progressive=True)
    buffer.seek(0)
    return buffer.getvalue()


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert():
    if "cover" not in request.files:
        return redirect(url_for("index"))

    file = request.files["cover"]
    if not file or file.filename.strip() == "":
        return redirect(url_for("index"))

    try:
        img = Image.open(file.stream)
    except Exception:
        return redirect(url_for("index"))

    converted_bytes = resize_for_routenote(img)
    original_name = Path(file.filename).stem or "cover"
    download_name = f"{original_name}_routenote_3000x3000.jpg"

    return send_file(
        io.BytesIO(converted_bytes),
        mimetype="image/jpeg",
        as_attachment=True,
        download_name=download_name,
        max_age=0
    )


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
