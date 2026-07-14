import traceback

# Monkey-patch print to show where it's called from
original_print = print
def print(*args, **kwargs):
    original_print(*args, **kwargs)
    # If it looks like a Keras config dump, show the source
    msg = str(args[0]) if args else ""
    if "categorical_crossentropy" in msg or "registered_name" in msg:
        original_print("⚠️ CONFIG DUMP COMING FROM:")
        traceback.print_stack()

import builtins
builtins.print = print


import os
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # Force CPU only
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

import numpy as np
import sys

# Add root to path so we can import from utils/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.preprocess import preprocess_image


import tensorflow as tf
tf.get_logger().setLevel('ERROR')
import warnings
warnings.filterwarnings('ignore')





# -----------------------------------------
# 1. CONFIG
# -----------------------------------------

MODEL_PATH       = "models/saved_model/potato_tomato_model.keras"
CLASS_NAMES_PATH = "models/saved_model/class_names.txt"

# Confidence thresholds
HIGH_CONFIDENCE   = 0.70   # above this -> full recommendation
MEDIUM_CONFIDENCE = 0.60   # between 0.60-0.70 -> warn uncertain
                           # below 0.60 -> ask to retake photo

# Supported crops - reject anything else
SUPPORTED_CROPS = ["potato", "tomato"]


# -----------------------------------------
# 2. LAZY LOAD MODEL + CLASS NAMES
# -----------------------------------------
# At top of predict.py
_MODEL = None
_CLASS_NAMES = None

def _load_model_and_classes():
    global _MODEL, _CLASS_NAMES
    if _MODEL is not None:
        return
    _MODEL = tf.keras.models.load_model(MODEL_PATH)
    with open(CLASS_NAMES_PATH, "r") as f:
        _CLASS_NAMES = [line.strip() for line in f.readlines()]


# -----------------------------------------
# 3. HELPER - EXTRACT CROP TYPE
# -----------------------------------------

def extract_crop_type(class_name: str) -> str:
    """
    Extracts crop type from class name.
    "Potato___Fungi"       -> "Potato"
    "Tomato___Late_blight" -> "Tomato"
    """
    return class_name.split("___")[0].strip()


# -----------------------------------------
# 4. HELPER - FORMAT CLASS NAME
# -----------------------------------------

def format_class_name(raw_name: str) -> str:
    """
    Converts raw class name to readable format.
    "Potato___Fungi"       -> "Potato Fungi"
    "Tomato___Late_blight" -> "Tomato Late Blight"
    """
    name = raw_name.replace("___", " ").replace("_", " ")
    return name.title()


# -----------------------------------------
# 5. PREDICT
# -----------------------------------------

def predict(image_input, crop_type=None):
    """
    Takes an image (file path or bytes),
    runs it through the model,
    returns a structured result dict.
    """
    
    # Load model on first use
    _load_model_and_classes()

    # Step 1 - preprocess image
    print(f"5️⃣ Image input type: {type(image_input)}")
    print(f"   Image input length: {len(image_input) if isinstance(image_input, bytes) else 'N/A'}")
    
    img_array = preprocess_image(image_input)
    print(f"6️⃣ Image preprocessed: {img_array.shape}")

    # Step 2 - run through model
    print("7️⃣ About to call model.predict...")
    predictions = _MODEL.predict(img_array, verbose=0)
    print(f"8️⃣ Predictions received: {predictions.shape}")
    
   

    # Step 3 - extract probabilities for single image
    probabilities = predictions[0]  # shape (17,)

    # Step 4 - Get top predicted class
    # If crop_type provided, only consider classes matching that crop
    if crop_type:
        filtered = [
            (i, probabilities[i])
            for i, name in enumerate(_CLASS_NAMES)
            if name.lower().startswith(crop_type.lower())
        ]
        top_index      = int(max(filtered, key=lambda x: x[1])[0])
    else:
        top_index      = int(np.argmax(probabilities))

    top_class_raw  = _CLASS_NAMES[top_index]
    top_confidence = float(probabilities[top_index])

    # Step 5 - format names for display
    disease_readable = format_class_name(top_class_raw)
    crop_type        = extract_crop_type(top_class_raw)

    # Step 6 - check if crop is supported
    # extra safety net — if unsupported crop sneaks through
    # with high confidence, we still catch it here
    is_supported = crop_type.lower() in SUPPORTED_CROPS

    # Step 7 - determine confidence level
    if top_confidence >= HIGH_CONFIDENCE and is_supported:
        confidence_level = "high"
    elif top_confidence >= MEDIUM_CONFIDENCE and is_supported:
        confidence_level = "medium"
    else:
        confidence_level = "low"

    # Step 8 - get top 3 predictions
    # useful to show farmer what else the model considered
    top3_indices = np.argsort(probabilities)[::-1][:3]
    top3 = {
        format_class_name(_CLASS_NAMES[i]): round(float(probabilities[i]), 4)
        for i in top3_indices
    }

    # Step 9 - build message based on confidence level
    confidence_pct = round(top_confidence * 100, 1)

    if confidence_level == "high":
        proceed = True
        message = (
            f"Detected: {disease_readable} "
            f"({confidence_pct}% confidence). "
            f"Fetching recommendation..."
        )
    elif confidence_level == "medium":
        proceed = True
        message = (
            f"Possible: {disease_readable} "
            f"({confidence_pct}% confidence). "
            f"Result is uncertain - please consult an agricultural "
            f"expert to confirm before applying any treatment."
        )
    else:
        proceed = False
        message = (
            f"तस्बिर स्पष्ट छैन वा यो आलु/गोलभेडाको पात होइन "
            f"({confidence_pct}% confidence). "
            f"कृपया आलु वा गोलभेडाको पातको स्पष्ट तस्बिर पठाउनुहोस्।"
        )

    return {
        "disease_raw"      : top_class_raw,
        "disease_readable" : disease_readable,
        "crop_type"        : crop_type,
        "confidence"       : round(top_confidence, 4),
        "confidence_pct"   : confidence_pct,
        "confidence_level" : confidence_level,
        "top3"             : top3,
        "proceed"          : proceed,
        "message"          : message,
    }


# -----------------------------------------
# 6. LOCAL TEST
# -----------------------------------------

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage: python model/predict.py <path_to_image>")
        sys.exit(1)

    image_path = sys.argv[1]

    print(f"\nRunning prediction on: {image_path}\n")
    result = predict(image_path)

    print("Prediction Result")
    print(f"  Disease (raw)      : {result['disease_raw']}")
    print(f"  Disease (readable) : {result['disease_readable']}")
    print(f"  Crop type          : {result['crop_type']}")
    print(f"  Confidence         : {result['confidence_pct']}%")
    print(f"  Confidence level   : {result['confidence_level']}")
    print(f"  Top 3 predictions  : {result['top3']}")
    print(f"\nMessage to app")
    print(f"  Proceed  : {result['proceed']}")
    print(f"  Message  : {result['message']}")