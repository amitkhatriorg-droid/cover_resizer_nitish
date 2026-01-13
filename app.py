from flask import Flask, request, send_file, jsonify, render_template
from PIL import Image, ImageOps
from io import BytesIO
import json

app = Flask(__name__)

# Prevent big uploads from failing (common cause of "Fail to fetch")
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024  # 40MB

TARGET = 3000

def _to_rgb_clean(im: Image.Image) -> Image.Image:
    # Fix EXIF orientation (then we re-encode => metadata effectively gone)
    im = ImageOps.exif_transpose(im)

    # Convert to RGB (handle alpha)
    if im.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", im.size, (0, 0, 0))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    elif im.mode != "RGB":
        im = im.convert("RGB")
    return im

def _clamp_crop(im: Image.Image, crop: dict):
    x = int(crop.get("x", 0))
    y = int(crop.get("y", 0))
    w = int(crop.get("w", im.width))
    h = int(crop.get("h", im.height))

    x = max(0, min(x, im.width - 1))
    y = max(0, min(y, im.height - 1))

    x2 = max(x + 1, min(x + w, im.width))
    y2 = max(y + 1, min(y + h, im.height))
    return (x, y, x2, y2)

def process_to_3000_jpeg(file_storage, crop=None) -> BytesIO:
    raw = file_storage.read()
    if not raw:
        raise ValueError("Empty upload")

    with Image.open(BytesIO(raw)) as im:
        im = _to_rgb_clean(im)

        if crop:
            im = im.crop(_clamp_crop(im, crop))

        # Premium: square center-crop + LANCZOS resize
        im = ImageOps.fit(
            im,
            (TARGET, TARGET),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )

        out = BytesIO()
        # MAX QUALITY JPEG (very high, still optimized)
        im.save(
            out,
            format="JPEG",
            quality=98,          # higher than 95 (more detail)
            optimize=True,
            progressive=True,
            subsampling=0        # 4:4:4 chroma (best)
        )
        out.seek(0)
        return out

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/convert", methods=["POST"])
def convert():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file uploaded"}), 400

    mode = request.form.get("mode", "auto")
    crop = None

    if mode == "manual":
        crop_raw = request.form.get("crop")
        if crop_raw:
            try:
                c = json.loads(crop_raw)
                crop = {"x": int(c["x"]), "y": int(c["y"]), "w": int(c["w"]), "h": int(c["h"])}
            except Exception:
                return jsonify({"error": "Invalid crop data"}), 400

    try:
        out = process_to_3000_jpeg(f, crop=crop)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return send_file(
        out,
        mimetype="image/jpeg",
        as_attachment=True,
        download_name="Cover_3000px_Premium.jpg",
        max_age=0
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
