from flask import Flask, request, send_file, jsonify, render_template
from PIL import Image, ImageOps
from io import BytesIO
import json

app = Flask(__name__)

TARGET = 3000

def process_image_to_3000_jpeg(file_storage, crop=None):
    data = file_storage.read()
    if not data:
        raise ValueError("Empty upload")

    bio = BytesIO(data)
    bio.seek(0)

    with Image.open(bio) as im:
        # Fix orientation using EXIF and then strip metadata by re-encoding clean
        im = ImageOps.exif_transpose(im)

        # Convert to RGB (handle alpha images)
        if im.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", im.size, (0, 0, 0))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        elif im.mode != "RGB":
            im = im.convert("RGB")

        # Manual crop (natural pixel coords)
        if crop:
            x = int(crop.get("x", 0))
            y = int(crop.get("y", 0))
            w = int(crop.get("w", im.width))
            h = int(crop.get("h", im.height))

            x = max(0, min(x, im.width - 1))
            y = max(0, min(y, im.height - 1))
            x2 = max(x + 1, min(x + w, im.width))
            y2 = max(y + 1, min(y + h, im.height))
            im = im.crop((x, y, x2, y2))

        # Premium square output without distortion (center fit/crop)
        im = ImageOps.fit(
            im,
            (TARGET, TARGET),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5)
        )

        out = BytesIO()
        # Metadata stripped: don't pass exif/info
        im.save(
            out,
            format="JPEG",
            quality=95,       # sweet spot = near-lossless look, smaller & faster
            optimize=True,
            progressive=True,
            subsampling=0     # 4:4:4 chroma = best quality
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
                crop = {
                    "x": int(c["x"]),
                    "y": int(c["y"]),
                    "w": int(c["w"]),
                    "h": int(c["h"])
                }
            except Exception:
                return jsonify({"error": "Invalid crop data"}), 400

    try:
        out = process_image_to_3000_jpeg(f, crop=crop)
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
