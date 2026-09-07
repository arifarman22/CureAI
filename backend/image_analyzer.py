"""
HuggingFace-powered medical image analysis.
Uses specialized models per image type with parallel fallback for speed.
"""
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

log = logging.getLogger(__name__)

# Model registry: type -> list of models tried in order
MODELS = {
    "skin": [
        "Anwarkh1/Skin_Disease-Image_Classification",
        "imfarzanansari/skintelligent-acne",
    ],
    "xray": [
        "nickmuchi/vit-finetuned-chest-xray-pneumonia",
        "lxyuan/vit-xray-pneumonia",
    ],
    "eye": [
        "martinezomg/vit-base-patch16-224-retinal-disease",
        "google/vit-base-patch16-224",
    ],
    "general": [
        "google/vit-base-patch16-224",
        "microsoft/resnet-50",
    ],
}

# Human-readable medical context per image type
TYPE_CONTEXT = {
    "skin": "skin condition or dermatological issue",
    "xray": "chest X-ray finding",
    "eye": "eye or retinal condition",
    "general": "medical condition",
}

HF_API = "https://router.huggingface.co/hf-inference/models/{}"
TIMEOUT = 20  # seconds per request


def _call_model(model: str, image_bytes: bytes, api_key: str) -> tuple[list, str] | None:
    """Call a single HuggingFace model. Returns (predictions, model_name) or None."""
    try:
        resp = requests.post(
            HF_API.format(model),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "image/jpeg"},
            data=image_bytes,
            timeout=TIMEOUT,
        )
        log.info(f"HF model {model}: status={resp.status_code} body={resp.text[:200]}")
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data and "label" in data[0]:
                return data, model
        elif resp.status_code == 503:
            log.warning(f"Model {model} is loading (503)")
        else:
            log.warning(f"Model {model} returned {resp.status_code}: {resp.text[:200]}")
    except requests.Timeout:
        log.warning(f"Model {model} timed out")
    except Exception as e:
        log.warning(f"Model {model} error: {e}")
    return None


def analyze_image(image_bytes: bytes, image_type: str, api_key: str) -> dict:
    """
    Analyze a medical image using HuggingFace Inference API.
    Tries models in parallel for speed, falls back gracefully.

    Returns:
        {
            "predictions": [...],
            "model": str,
            "image_type": str,
            "analysis": str,
            "confidence": "high" | "medium" | "low"
        }
    """
    if not api_key:
        return _fallback_response(image_type)

    image_type = image_type if image_type in MODELS else "general"
    models = MODELS[image_type]

    predictions, model_used = None, None

    # Try models in parallel (max 2 at a time) for faster response
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(_call_model, m, image_bytes, api_key): m for m in models}
        for future in as_completed(futures):
            result = future.result()
            if result:
                predictions, model_used = result
                # Cancel remaining futures once we have a result
                for f in futures:
                    f.cancel()
                break

    if not predictions:
        return _fallback_response(image_type)

    top = predictions[:5]
    analysis = _build_analysis(top, image_type, model_used)
    confidence = "high" if top[0].get("score", 0) > 0.6 else "medium"

    return {
        "predictions": top,
        "model": model_used,
        "image_type": image_type,
        "analysis": analysis,
        "confidence": confidence,
    }


def _build_analysis(predictions: list, image_type: str, model: str) -> str:
    """Build a structured medical analysis string from predictions."""
    context = TYPE_CONTEXT.get(image_type, "medical condition")
    top = predictions[0]
    label = top.get("label", "Unknown").replace("_", " ").title()
    score = top.get("score", 0)

    lines = [f"**Medical Image Analysis — {context.title()}**\n"]

    # Top finding
    lines.append(f"**Primary Finding:** {label} ({score:.1%} confidence)\n")

    # All predictions
    lines.append("**Classification Results:**")
    for i, p in enumerate(predictions, 1):
        lbl = p.get("label", "?").replace("_", " ").title()
        sc = p.get("score", 0)
        bar = "█" * int(sc * 10) + "░" * (10 - int(sc * 10))
        lines.append(f"{i}. {lbl} — {bar} {sc:.1%}")

    # Type-specific medical guidance
    lines.append("")
    lines.append(_get_medical_guidance(label, image_type, score))

    lines.append("\n---")
    lines.append("⚠️ **Disclaimer:** This is an AI-based preliminary screening only. "
                 "It is NOT a medical diagnosis. Please consult a qualified healthcare professional "
                 "for proper evaluation and treatment.")

    return "\n".join(lines)


def _get_medical_guidance(label: str, image_type: str, score: float) -> str:
    """Return type-specific medical guidance based on detected condition."""
    label_lower = label.lower()

    if image_type == "skin":
        if any(w in label_lower for w in ["melanoma", "carcinoma", "cancer", "malignant"]):
            return ("**⚠️ Urgent:** The AI detected a potentially serious skin condition. "
                    "Please consult a dermatologist immediately for a biopsy and professional evaluation.")
        elif any(w in label_lower for w in ["acne", "pimple"]):
            return ("**Acne detected.** Common treatments include topical retinoids, benzoyl peroxide, "
                    "or salicylic acid. A dermatologist can prescribe stronger treatments if needed.")
        elif any(w in label_lower for w in ["eczema", "dermatitis"]):
            return ("**Eczema/Dermatitis detected.** Keep skin moisturized, avoid triggers. "
                    "Topical corticosteroids may help. Consult a dermatologist for persistent cases.")
        elif any(w in label_lower for w in ["psoriasis"]):
            return ("**Psoriasis detected.** A chronic condition requiring medical management. "
                    "Consult a dermatologist for topical or systemic treatment options.")
        else:
            return ("**Recommendation:** Consult a dermatologist for proper evaluation of this skin condition. "
                    "Monitor for changes in size, color, or shape.")

    elif image_type == "xray":
        if any(w in label_lower for w in ["pneumonia", "infection", "opacity"]):
            return ("**⚠️ Possible Pneumonia detected.** Symptoms include fever, cough, and difficulty breathing. "
                    "Seek medical attention promptly. Treatment typically involves antibiotics or antivirals.")
        elif any(w in label_lower for w in ["normal", "clear"]):
            return ("**Chest X-ray appears normal.** No obvious abnormalities detected. "
                    "If you have symptoms, consult a doctor as X-rays may not detect all conditions.")
        else:
            return ("**Abnormality detected.** Please consult a pulmonologist or general physician "
                    "for a thorough evaluation of this chest X-ray finding.")

    elif image_type == "eye":
        if any(w in label_lower for w in ["diabetic", "retinopathy"]):
            return ("**⚠️ Diabetic Retinopathy signs detected.** This requires urgent ophthalmologist evaluation. "
                    "Early treatment can prevent vision loss.")
        elif any(w in label_lower for w in ["cataract"]):
            return ("**Cataract detected.** Cataracts are treatable with surgery. "
                    "Consult an ophthalmologist to discuss treatment options.")
        elif any(w in label_lower for w in ["glaucoma"]):
            return ("**⚠️ Glaucoma signs detected.** This is a serious condition that can cause vision loss. "
                    "Consult an ophthalmologist immediately.")
        else:
            return ("**Recommendation:** Consult an ophthalmologist for a comprehensive eye examination "
                    "to properly evaluate this finding.")

    else:
        return ("**Recommendation:** Based on the AI analysis, please consult the appropriate medical specialist "
                "for a professional evaluation of these findings.")


def _fallback_response(image_type: str) -> dict:
    context = TYPE_CONTEXT.get(image_type, "medical condition")
    guidance = {
        "skin": ("Please describe the skin condition in the chat (color, size, texture, duration) "
                 "for text-based analysis. Consult a dermatologist for proper evaluation."),
        "xray": ("For chest X-ray analysis, ensure the image is clear and properly oriented. "
                 "Always have X-rays reviewed by a radiologist or physician."),
        "eye": ("For eye condition analysis, ensure the image is well-lit and focused. "
                "Consult an ophthalmologist for proper evaluation."),
        "general": ("Please describe your symptoms in the chat for text-based analysis. "
                    "Consult a healthcare professional for proper evaluation."),
    }
    return {
        "predictions": [],
        "model": "fallback",
        "image_type": image_type,
        "confidence": "low",
        "analysis": (
            f"**Image Analysis — {context.title()}**\n\n"
            "The AI image analysis service is temporarily unavailable.\n\n"
            f"**Recommendation:** {guidance.get(image_type, guidance['general'])}\n\n"
            "⚠️ Always consult a qualified healthcare professional for medical concerns."
        ),
    }
