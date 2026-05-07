import os
import re
import html
import uuid
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from models import Chat, Message, db
from config.settings import (
    MAX_IMAGE_SIZE_MB, ALLOWED_IMAGE_EXTENSIONS,
    MAX_MESSAGE_LENGTH, MAX_CHAT_TITLE_LENGTH,
)

log = logging.getLogger(__name__)
chat_bp = Blueprint("chat", __name__)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_CHATS_PER_USER = 100


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def validate_uuid(value):
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def sanitize_content(text, max_len):
    """Sanitize user-provided content: strip, truncate, remove control chars."""
    if not text:
        return ""
    cleaned = text.strip()[:max_len]
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', cleaned)
    return cleaned


# --- Chat CRUD ---

@chat_bp.route("/chats", methods=["GET"])
@jwt_required()
def get_chats():
    try:
        user_id = get_jwt_identity()
        chats = Chat.query.filter_by(user_id=user_id).order_by(Chat.updated_at.desc()).all()
        return jsonify({"chats": [c.to_dict() for c in chats]}), 200
    except Exception as e:
        log.exception("Error loading chats")
        return jsonify({"error": "Failed to load chats"}), 500


@chat_bp.route("/chats", methods=["POST"])
@jwt_required()
def create_chat():
    try:
        user_id = get_jwt_identity()

        # Limit total chats per user
        chat_count = Chat.query.filter_by(user_id=user_id).count()
        if chat_count >= MAX_CHATS_PER_USER:
            return jsonify({"error": f"Maximum {MAX_CHATS_PER_USER} chats reached. Delete old chats to continue."}), 400

        data = request.get_json(silent=True) or {}
        title = sanitize_content(data.get("title", ""), MAX_CHAT_TITLE_LENGTH)
        if not title:
            title = f"Chat {datetime.now().strftime('%b %d, %H:%M')}"

        chat = Chat(user_id=user_id, title=title)
        db.session.add(chat)
        db.session.commit()
        return jsonify({"message": "Chat created", "chat": chat.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        log.exception("Error creating chat")
        return jsonify({"error": "Failed to create chat"}), 500


@chat_bp.route("/chats/<chat_id>", methods=["GET"])
@jwt_required()
def get_chat_messages(chat_id):
    try:
        if not validate_uuid(chat_id):
            return jsonify({"error": "Invalid chat ID"}), 400

        user_id = get_jwt_identity()
        chat = Chat.query.filter_by(id=chat_id, user_id=user_id).first()
        if not chat:
            return jsonify({"error": "Chat not found"}), 404

        messages = chat.messages.order_by(Message.timestamp.asc()).all()
        return jsonify({"chat": chat.to_dict(), "messages": [m.to_dict() for m in messages]}), 200

    except Exception as e:
        log.exception("Error loading chat messages")
        return jsonify({"error": "Failed to load messages"}), 500


@chat_bp.route("/chats/<chat_id>/messages", methods=["POST"])
@jwt_required()
def add_message(chat_id):
    try:
        if not validate_uuid(chat_id):
            return jsonify({"error": "Invalid chat ID"}), 400

        user_id = get_jwt_identity()
        chat = Chat.query.filter_by(id=chat_id, user_id=user_id).first()
        if not chat:
            return jsonify({"error": "Chat not found"}), 404

        data = request.get_json(silent=True) or {}
        content = sanitize_content(data.get("content", ""), MAX_MESSAGE_LENGTH)
        sender = data.get("sender", "user")

        if not content:
            return jsonify({"error": "Message content is required"}), 400
        if len(content) > MAX_MESSAGE_LENGTH:
            return jsonify({"error": f"Message too long. Max {MAX_MESSAGE_LENGTH} characters."}), 400
        if sender not in ("user", "ai"):
            return jsonify({"error": "Invalid sender"}), 400

        msg = Message(chat_id=chat_id, content=content, sender=sender, message_type="text")
        db.session.add(msg)
        chat.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"message": "Message added", "data": msg.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        log.exception("Error adding message")
        return jsonify({"error": "Failed to add message"}), 500


@chat_bp.route("/chats/<chat_id>", methods=["DELETE"])
@jwt_required()
def delete_chat(chat_id):
    try:
        if not validate_uuid(chat_id):
            return jsonify({"error": "Invalid chat ID"}), 400

        user_id = get_jwt_identity()
        chat = Chat.query.filter_by(id=chat_id, user_id=user_id).first()
        if not chat:
            return jsonify({"error": "Chat not found"}), 404

        # Delete associated uploaded images from disk
        for msg in chat.messages.filter_by(message_type="image").all():
            if msg.image_filename:
                filepath = os.path.join(UPLOAD_DIR, secure_filename(msg.image_filename))
                if os.path.exists(filepath):
                    os.remove(filepath)

        db.session.delete(chat)
        db.session.commit()
        return jsonify({"message": "Chat deleted"}), 200

    except Exception as e:
        db.session.rollback()
        log.exception("Error deleting chat")
        return jsonify({"error": "Failed to delete chat"}), 500


@chat_bp.route("/chats/<chat_id>/title", methods=["PUT"])
@jwt_required()
def update_chat_title(chat_id):
    try:
        if not validate_uuid(chat_id):
            return jsonify({"error": "Invalid chat ID"}), 400

        user_id = get_jwt_identity()
        chat = Chat.query.filter_by(id=chat_id, user_id=user_id).first()
        if not chat:
            return jsonify({"error": "Chat not found"}), 404

        data = request.get_json(silent=True) or {}
        title = sanitize_content(data.get("title", ""), MAX_CHAT_TITLE_LENGTH)
        if not title:
            return jsonify({"error": "Title is required"}), 400

        chat.title = title
        chat.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"message": "Title updated", "chat": chat.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        log.exception("Error updating chat title")
        return jsonify({"error": "Failed to update title"}), 500


# --- Image Upload ---

@chat_bp.route("/chats/<chat_id>/upload", methods=["POST"])
@jwt_required()
def upload_image(chat_id):
    try:
        if not validate_uuid(chat_id):
            return jsonify({"error": "Invalid chat ID"}), 400

        user_id = get_jwt_identity()
        chat = Chat.query.filter_by(id=chat_id, user_id=user_id).first()
        if not chat:
            return jsonify({"error": "Chat not found"}), 404

        if "image" not in request.files:
            return jsonify({"error": "No image file provided"}), 400

        file = request.files["image"]
        if not file.filename or not allowed_file(file.filename):
            return jsonify({"error": f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"}), 400

        # Check file size
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        if size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            return jsonify({"error": f"File too large. Max {MAX_IMAGE_SIZE_MB}MB"}), 400
        if size == 0:
            return jsonify({"error": "Empty file"}), 400

        # Validate image magic bytes
        header = file.read(8)
        file.seek(0)
        if not _is_valid_image_header(header):
            return jsonify({"error": "File does not appear to be a valid image"}), 400

        ext = file.filename.rsplit(".", 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(UPLOAD_DIR, filename))

        caption = (request.form.get("caption", "") or "Uploaded an image for analysis").strip()[:MAX_MESSAGE_LENGTH]

        msg = Message(
            chat_id=chat_id,
            content=caption,
            sender="user",
            message_type="image",
            image_filename=filename,
        )
        db.session.add(msg)
        chat.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({"message": "Image uploaded", "data": msg.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        log.exception("Error uploading image")
        return jsonify({"error": "Failed to upload image"}), 500


def _is_valid_image_header(header):
    """Check magic bytes to verify the file is actually an image."""
    if len(header) < 4:
        return False
    # PNG
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return True
    # JPEG
    if header[:3] == b'\xff\xd8\xff':
        return True
    # BMP
    if header[:2] == b'BM':
        return True
    # WEBP
    if header[:4] == b'RIFF' and len(header) >= 8:
        return True
    return False


@chat_bp.route("/uploads/<filename>", methods=["GET"])
@jwt_required()
def serve_upload(filename):
    """Serve uploaded files with path traversal protection."""
    safe = secure_filename(filename)
    if not safe or safe != filename:
        return jsonify({"error": "Invalid filename"}), 400

    filepath = os.path.join(UPLOAD_DIR, safe)
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404

    return send_from_directory(UPLOAD_DIR, safe)
