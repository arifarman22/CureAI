import os
import logging
import requests as http_requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity, get_jwt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config.settings import (
    DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY,
    JWT_ACCESS_TOKEN_EXPIRES_MINUTES, ALLOWED_ORIGINS,
    HUGGINGFACE_API_KEY, PINECONE_API_KEY,
    RATE_LIMIT_DEFAULT, RATE_LIMIT_AUTH, RATE_LIMIT_PREDICT,
    ALLOWED_IMAGE_EXTENSIONS, MAX_IMAGE_SIZE_MB, MAX_SYMPTOM_LENGTH,
)
from models import db, User, Chat, Message, TokenBlocklist
from auth import auth_bp
from chat_routes import chat_bp

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

# --- App ---
app = Flask(__name__, static_folder="../frontend/static", static_url_path="")

app.config["SECRET_KEY"] = SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_size": 10,
    "max_overflow": 20,
    "connect_args": {"sslmode": "require"} if "neon.tech" in DATABASE_URL else {},
}

app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRES_MINUTES)
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_HEADER_NAME"] = "Authorization"
app.config["JWT_HEADER_TYPE"] = "Bearer"
app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_SIZE_MB * 1024 * 1024

# --- Extensions ---
db.init_app(app)
jwt = JWTManager(app)
CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[RATE_LIMIT_DEFAULT],
    storage_uri="memory://",
)
limiter.limit(RATE_LIMIT_AUTH)(auth_bp)


# --- Token Blocklist ---
@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    return TokenBlocklist.query.filter_by(jti=jwt_payload["jti"]).first() is not None


# --- Security Headers ---
@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    allowed = " ".join(ALLOWED_ORIGINS)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data: blob:; "
        f"connect-src 'self' {allowed}"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


# --- JWT Error Handlers ---
@jwt.expired_token_loader
def expired_token(jwt_header, jwt_payload):
    return jsonify({"error": "Token has expired", "code": "TOKEN_EXPIRED"}), 401

@jwt.invalid_token_loader
def invalid_token(error):
    return jsonify({"error": "Invalid token", "code": "INVALID_TOKEN"}), 401

@jwt.unauthorized_loader
def missing_token(error):
    return jsonify({"error": "Authorization required", "code": "NO_TOKEN"}), 401

@jwt.revoked_token_loader
def revoked_token(jwt_header, jwt_payload):
    return jsonify({"error": "Token has been revoked", "code": "TOKEN_REVOKED"}), 401


# --- Global Error Handlers ---
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(413)
def payload_too_large(e):
    return jsonify({"error": f"File too large. Maximum size is {MAX_IMAGE_SIZE_MB}MB"}), 413

@app.errorhandler(429)
def rate_limit_exceeded(e):
    return jsonify({"error": "Too many requests. Please slow down."}), 429

@app.errorhandler(500)
def internal_error(e):
    log.exception("Unhandled server error")
    return jsonify({"error": "Internal server error"}), 500


# --- Blueprints ---
app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(chat_bp, url_prefix="/api")


# --- Serve Frontend ---
@app.route("/")
def serve_index():
    return app.send_static_file("index.html")

@app.route("/<path:path>")
def serve_static(path):
    try:
        return app.send_static_file(path)
    except Exception:
        return app.send_static_file("index.html")


# =====================================================
# AI ENGINE — Pinecone Retrieval + OpenAI/HF Generation
# =====================================================

# Global AI components
vector_store = None
openai_client = None
AI_MODE = "fallback"  # "openai", "pinecone_only", or "fallback"


def initialize_ai():
    """Initialize AI: Pinecone for retrieval, OpenAI for generation."""
    global vector_store, openai_client, AI_MODE

    # --- Step 1: Pinecone Vector Store ---
    if PINECONE_API_KEY:
        try:
            from sentence_transformers import SentenceTransformer
            from pinecone import Pinecone

            pc = Pinecone(api_key=PINECONE_API_KEY)
            index_name = "test"  # Your existing index with Medical PDF data

            if index_name in [idx.name for idx in pc.list_indexes()]:
                vector_store = {
                    "index": pc.Index(index_name),
                    "model": SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2"),
                }
                AI_MODE = "pinecone_only"
                log.info(f"Pinecone connected to index '{index_name}'")
            else:
                log.warning(f"Pinecone index '{index_name}' not found")
        except ImportError:
            log.warning("sentence-transformers or pinecone not installed")
        except Exception as e:
            log.exception("Pinecone init error")

    # --- Step 2: OpenAI (optional, for better generation) ---
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        try:
            from openai import OpenAI
            openai_client = OpenAI(api_key=openai_key)
            # Quick validation
            openai_client.models.list()
            AI_MODE = "openai" if vector_store else "openai"
            log.info("OpenAI connected")
        except Exception as e:
            log.warning(f"OpenAI not available: {e}")
            openai_client = None

    log.info(f"AI Mode: {AI_MODE}")


def _pinecone_query(query, top_k=3, filter_dict=None):
    """Low-level Pinecone query helper."""
    if not vector_store:
        return []
    try:
        embedding = vector_store["model"].encode(query).tolist()
        kwargs = {"vector": embedding, "top_k": top_k, "include_metadata": True}
        if filter_dict:
            kwargs["filter"] = filter_dict
        results = vector_store["index"].query(**kwargs)
        contexts = []
        matches = results.get("matches", []) if isinstance(results, dict) else getattr(results, "matches", [])
        for match in matches:
            meta = match.get("metadata", {}) if isinstance(match, dict) else getattr(match, "metadata", {})
            score = match.get("score", 0) if isinstance(match, dict) else getattr(match, "score", 0)
            text = meta.get("text", "") or meta.get("page_content", "")
            if text:
                contexts.append({"text": text[:500], "score": round(score, 3), "source": meta.get("source", "")})
        return contexts
    except Exception as e:
        log.exception("Pinecone query error")
        return []


def search_medical_knowledge(query, top_k=3):
    """Search Pinecone for relevant medical context from your PDF."""
    return _pinecone_query(query, top_k=top_k)


def search_medicines(query, top_k=3):
    """Search Pinecone specifically for medicine recommendations."""
    return _pinecone_query(query, top_k=top_k, filter_dict={"source": "medex.com.bd"})


def generate_with_openai(symptoms, contexts):
    """Generate medical response using OpenAI with retrieved context."""
    if not openai_client:
        return None

    context_text = "\n\n".join([f"Medical Reference:\n{c['text']}" for c in contexts]) if contexts else "No specific medical references available."

    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are CureAI, a professional medical assistant. "
                        "Analyze the patient's symptoms using the provided medical references. "
                        "Provide: 1) Possible conditions 2) Severity assessment 3) Home care advice "
                        "4) When to see a doctor. Always remind this is not a definitive diagnosis."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Medical References:\n{context_text}\n\nPatient's symptoms: {symptoms}",
                },
            ],
            temperature=0.7,
            max_tokens=800,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        log.exception("OpenAI generation error")
        return None


def build_context_response(symptoms, contexts, medicines=None):
    """Build a detailed response from Pinecone search results + medicine data."""
    if not contexts and not medicines:
        return get_smart_fallback(symptoms)

    lines = []

    if contexts:
        lines.append("Based on your symptoms and our medical knowledge base, here's what I found:\n")
        for i, ctx in enumerate(contexts, 1):
            lines.append(f"**Medical Reference {i}** (relevance: {ctx['score']:.0%}):")
            lines.append(f"{ctx['text']}\n")

    lines.append("---\n")
    lines.append("**My Assessment:**\n")
    lines.append(analyze_symptoms(symptoms))

    if medicines:
        lines.append("\n---\n")
        lines.append("**Suggested Medicines (Bangladesh):**\n")
        for i, med in enumerate(medicines, 1):
            lines.append(f"{i}. {med['text'][:300]}\n")
        lines.append("*Always consult a doctor or pharmacist before taking any medication.*")

    lines.append("\n**Important:** The above references are from medical literature. "
                 "Please consult a healthcare professional for proper diagnosis and treatment.")

    return "\n".join(lines)


def analyze_symptoms(symptoms):
    """Rule-based symptom analysis for common conditions."""
    s = symptoms.lower()
    findings = []

    # Fever analysis
    if any(w in s for w in ["fever", "temperature", "hot", "chills"]):
        findings.append("**Fever Assessment:**")
        if any(w in s for w in ["3 day", "three day", "few day", "several day"]):
            findings.append("- A fever lasting 3+ days may indicate a viral or bacterial infection")
            findings.append("- Common causes: Influenza, COVID-19, urinary tract infection, sinusitis, pneumonia")
        if any(w in s for w in ["high fever", "103", "104", "39", "40"]):
            findings.append("- **HIGH FEVER** - Seek medical attention promptly")
        findings.append("- **Home care:** Stay hydrated, rest, use acetaminophen or ibuprofen as directed")
        findings.append("- **See a doctor if:** Fever exceeds 103F/39.4C, lasts more than 3 days, or is accompanied by severe symptoms")

    # Headache
    if any(w in s for w in ["headache", "head pain", "head ache", "migraine"]):
        findings.append("\n**Headache Assessment:**")
        findings.append("- Could indicate: Tension headache, migraine, sinusitis, dehydration, or stress")
        findings.append("- **Home care:** Rest in a dark room, stay hydrated, try OTC pain relievers")
        findings.append("- **See a doctor if:** Sudden severe headache, vision changes, neck stiffness, or confusion")

    # Cough / respiratory
    if any(w in s for w in ["cough", "cold", "sore throat", "throat", "breathing", "congestion", "runny nose"]):
        findings.append("\n**Respiratory Assessment:**")
        findings.append("- Could indicate: Common cold, flu, COVID-19, bronchitis, allergies, or sinusitis")
        findings.append("- **Home care:** Warm fluids, honey for cough, steam inhalation, rest")
        findings.append("- **See a doctor if:** Difficulty breathing, chest pain, coughing blood, or symptoms worsening after 7 days")

    # Stomach / digestive
    if any(w in s for w in ["stomach", "nausea", "vomit", "diarrhea", "abdomen", "belly", "digest", "bloat"]):
        findings.append("\n**Digestive Assessment:**")
        findings.append("- Could indicate: Gastroenteritis, food poisoning, IBS, acid reflux, or appendicitis")
        findings.append("- **Home care:** BRAT diet (bananas, rice, applesauce, toast), clear fluids, avoid dairy")
        findings.append("- **See a doctor if:** Severe abdominal pain, blood in stool, persistent vomiting, or signs of dehydration")

    # Pain
    if any(w in s for w in ["pain", "ache", "hurt", "sore"]):
        if any(w in s for w in ["chest", "heart"]):
            findings.append("\n**CHEST PAIN - URGENT:**")
            findings.append("- **Seek emergency care immediately if you have chest pain with shortness of breath, sweating, or pain radiating to arm/jaw**")
        elif any(w in s for w in ["back", "spine"]):
            findings.append("\n**Back Pain Assessment:**")
            findings.append("- Could indicate: Muscle strain, herniated disc, poor posture, or kidney issues")
            findings.append("- **Home care:** Gentle stretching, heat/ice therapy, OTC pain relievers")
        elif any(w in s for w in ["joint", "knee", "elbow", "wrist"]):
            findings.append("\n**Joint Pain Assessment:**")
            findings.append("- Could indicate: Arthritis, injury, gout, or overuse")
            findings.append("- **Home care:** Rest, ice, compression, elevation (RICE)")

    # Skin
    if any(w in s for w in ["rash", "skin", "itch", "bump", "acne", "pimple", "swelling"]):
        findings.append("\n**Skin Assessment:**")
        findings.append("- Could indicate: Allergic reaction, eczema, dermatitis, infection, or other skin condition")
        findings.append("- **Home care:** Keep area clean, avoid scratching, use antihistamines for itching")
        findings.append("- **See a doctor if:** Rapidly spreading rash, fever with rash, or signs of infection")

    # Fatigue
    if any(w in s for w in ["tired", "fatigue", "exhausted", "weak", "energy"]):
        findings.append("\n**Fatigue Assessment:**")
        findings.append("- Could indicate: Anemia, thyroid issues, sleep disorders, depression, or viral infection")
        findings.append("- **Home care:** Ensure 7-9 hours of sleep, balanced diet, regular exercise")
        findings.append("- **See a doctor if:** Persistent fatigue lasting more than 2 weeks")

    if not findings:
        findings.append("Based on your description, I recommend consulting a healthcare professional for a thorough evaluation.")
        findings.append("- **Track your symptoms:** When they started, severity (1-10), triggers, and any changes")
        findings.append("- **Stay hydrated** and get adequate rest")
        findings.append("- **Seek immediate care if:** You experience severe pain, difficulty breathing, or sudden worsening")

    return "\n".join(findings)


def get_smart_fallback(symptoms):
    """Intelligent fallback when no Pinecone results are found."""
    return f"I've analyzed your symptoms. Here's my assessment:\n\n{analyze_symptoms(symptoms)}\n\n" \
           "**Note:** For the most accurate diagnosis, please consult a healthcare professional. " \
           "This analysis is based on general medical knowledge and should not replace professional medical advice."


# --- Image Analysis ---

# Common medical image conditions for rule-based analysis
SKIN_CONDITIONS = {
    "redness": "Possible dermatitis, sunburn, or allergic reaction",
    "rash": "Could indicate eczema, psoriasis, or contact dermatitis",
    "swelling": "May suggest inflammation, infection, or allergic reaction",
    "wound": "Assess for infection signs: redness, warmth, pus, or spreading",
    "bruise": "Usually heals on its own; see a doctor if unexplained or frequent",
}


def analyze_image_with_hf(image_bytes):
    """Try HuggingFace image classification."""
    if not HUGGINGFACE_API_KEY:
        return None

    models_to_try = [
        "google/vit-base-patch16-224",
        "microsoft/resnet-50",
    ]

    for model in models_to_try:
        try:
            resp = http_requests.post(
                f"https://api-inference.huggingface.co/models/{model}",
                headers={"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"},
                data=image_bytes,
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json(), model
        except Exception:
            continue

    return None, None


# --- Routes ---

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "ai_mode": AI_MODE,
        "pinecone": vector_store is not None,
        "openai": openai_client is not None,
    }), 200


@app.route("/api/predict", methods=["POST"])
@jwt_required()
@limiter.limit(RATE_LIMIT_PREDICT)
def predict():
    try:
        data = request.get_json(silent=True) or {}
        symptoms = data.get("symptoms", "").strip()

        if not symptoms:
            return jsonify({"error": "No symptoms provided"}), 400
        if len(symptoms) > MAX_SYMPTOM_LENGTH:
            return jsonify({"error": f"Input too long. Max {MAX_SYMPTOM_LENGTH} characters."}), 400

        # Step 1: Search medical knowledge + medicines
        contexts = search_medical_knowledge(symptoms)
        medicines = search_medicines(symptoms)
        source_docs = [{"content": c["text"][:200], "score": c["score"]} for c in contexts]

        # Step 2: Generate response
        if openai_client:
            all_context = contexts + [{"text": f"[MEDICINE] {m['text']}", "score": m["score"]} for m in medicines]
            diagnosis = generate_with_openai(symptoms, all_context)
            if diagnosis:
                return jsonify({
                    "diagnosis": diagnosis,
                    "confidence": "high",
                    "source": "openai+pinecone",
                    "source_documents": source_docs,
                })

        if contexts or medicines:
            diagnosis = build_context_response(symptoms, contexts, medicines)
            return jsonify({
                "diagnosis": diagnosis,
                "confidence": "medium",
                "source": "pinecone+rules",
                "source_documents": source_docs,
            })

        return jsonify({
            "diagnosis": get_smart_fallback(symptoms),
            "confidence": "medium",
            "source": "rules",
            "source_documents": [],
        })

    except Exception as e:
        log.exception("Predict endpoint error")
        return jsonify({"error": "Failed to process your request"}), 500


@app.route("/api/predict-image", methods=["POST"])
@jwt_required()
@limiter.limit(RATE_LIMIT_PREDICT)
def predict_image():
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image provided"}), 400

        file = request.files["image"]
        if not file.filename:
            return jsonify({"error": "Empty filename"}), 400

        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            return jsonify({"error": f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"}), 400

        image_bytes = file.read()
        if not image_bytes:
            return jsonify({"error": "Empty file"}), 400

        # Try HuggingFace image classification
        predictions, model_used = analyze_image_with_hf(image_bytes)

        if predictions and isinstance(predictions, list):
            # If we have OpenAI, get a medical interpretation
            if openai_client:
                pred_text = ", ".join([f"{p.get('label', '?')} ({p.get('score', 0):.1%})" for p in predictions[:5]])
                try:
                    resp = openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are a medical image analysis assistant. Interpret image classification results in a medical context. Be helpful but always recommend professional consultation."},
                            {"role": "user", "content": f"Image classification results: {pred_text}\nProvide a medical interpretation of what this image might show."},
                        ],
                        temperature=0.7,
                        max_tokens=500,
                    )
                    analysis = resp.choices[0].message.content.strip()
                except Exception:
                    analysis = format_image_predictions(predictions)
            else:
                analysis = format_image_predictions(predictions)

            return jsonify({
                "analysis": analysis,
                "predictions": predictions[:5],
                "confidence": "medium",
                "model": model_used,
            })

        # Fallback
        return jsonify({
            "analysis": get_image_fallback_response(),
            "confidence": "low",
            "model": "fallback",
        })

    except http_requests.Timeout:
        return jsonify({"error": "Image analysis timed out. Please try again."}), 504
    except Exception as e:
        log.exception("Image analysis error")
        return jsonify({
            "analysis": get_image_fallback_response(),
            "confidence": "low",
            "model": "fallback",
        })


def format_image_predictions(predictions):
    if not isinstance(predictions, list) or not predictions:
        return get_image_fallback_response()
    lines = ["**Image Analysis Results:**\n"]
    for i, pred in enumerate(predictions[:5], 1):
        label = pred.get("label", "Unknown")
        score = pred.get("score", 0)
        lines.append(f"{i}. **{label}** - {score:.1%} confidence")
    lines.append("\n**Medical Note:** General image classification was used. "
                 "For accurate medical image analysis, please consult a dermatologist or relevant specialist.")
    lines.append("\n**Important:** This is an AI-based preliminary analysis. "
                 "It should NOT be used as a medical diagnosis.")
    return "\n".join(lines)


def get_image_fallback_response():
    return ("I've received your image. Here's what I recommend:\n\n"
            "**For skin conditions:**\n"
            "1. Note the size, color, shape, and any changes over time\n"
            "2. Check if it's itchy, painful, or spreading\n"
            "3. Take photos over several days to track changes\n\n"
            "**For injuries:**\n"
            "1. Clean the area gently with mild soap and water\n"
            "2. Apply appropriate first aid\n"
            "3. Watch for signs of infection (redness, warmth, swelling, pus)\n\n"
            "**Next steps:**\n"
            "- Describe what you see in the chat for text-based analysis\n"
            "- Consult a healthcare provider for professional evaluation\n\n"
            "**Disclaimer:** AI image analysis is not a substitute for professional medical diagnosis.")


# --- Cleanup ---
def cleanup_expired_tokens():
    with app.app_context():
        expired = TokenBlocklist.query.filter(TokenBlocklist.expires_at < datetime.utcnow()).all()
        for t in expired:
            db.session.delete(t)
        if expired:
            db.session.commit()
            log.info(f"Cleaned up {len(expired)} expired blocklist entries.")


def create_tables():
    with app.app_context():
        db.create_all()
        log.info("Database tables ready.")


# --- Startup ---
def startup():
    create_tables()
    cleanup_expired_tokens()
    initialize_ai()

startup()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
