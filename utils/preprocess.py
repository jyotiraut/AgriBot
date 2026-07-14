import numpy as np
from PIL import Image
import io

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

# Must match the image size used during training in Colab
# EfficientNetB3 expects 300x300
IMG_SIZE = (300, 300)


# ─────────────────────────────────────────
# PREPROCESS FUNCTION
# ─────────────────────────────────────────

def preprocess_image(image_input):
    """
    Accepts either:
      - a file path (string)  → for local testing
      - raw bytes             → for FastAPI file uploads

    Steps:
      1. Open the image
      2. Convert to RGB (removes alpha channel if PNG, handles grayscale)
      3. Resize to 300x300 (EfficientNetB3 input size)
      4. Convert to numpy array
      5. Add batch dimension → shape (1, 300, 300, 3)

    Returns:
      numpy array of shape (1, 300, 300, 3) ready for model.predict()
    """

    # ── Step 1 & 2 — Open and convert to RGB ──
    if isinstance(image_input, bytes):
        # Coming from FastAPI upload — raw bytes
        img = Image.open(io.BytesIO(image_input)).convert("RGB")

    elif isinstance(image_input, str):
        # Coming from local test — file path
        img = Image.open(image_input).convert("RGB")

    else:
        raise ValueError(
            "image_input must be a file path (string) or raw bytes. "
            f"Got: {type(image_input)}"
        )

    # ── Step 3 — Resize ──
    img = img.resize(IMG_SIZE)

    # ── Step 4 — Convert to numpy array ──
    # Shape becomes (300, 300, 3)
    img_array = np.array(img, dtype=np.float32)

    # ── Step 5 — Add batch dimension ──
    # Shape becomes (1, 300, 300, 3)
    # Model always expects a batch even for single image
    img_array = np.expand_dims(img_array, axis=0)

    # Note: No manual normalization (dividing by 255) needed here.
    # EfficientNetB3 has built-in normalization inside the model itself.

    return img_array


# ─────────────────────────────────────────
# QUICK LOCAL TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python utils/preprocess.py <path_to_image>")
        sys.exit(1)

    image_path = sys.argv[1]

    print(f"Testing preprocess on: {image_path}")
    result = preprocess_image(image_path)

    print(f"✅ Preprocessing successful!")
    print(f"   Input  : {image_path}")
    print(f"   Output shape : {result.shape}")       # should be (1, 300, 300, 3)
    print(f"   Output dtype : {result.dtype}")       # should be float32
    print(f"   Min pixel    : {result.min():.2f}")   # should be 0.0
    print(f"   Max pixel    : {result.max():.2f}")   # should be 255.0