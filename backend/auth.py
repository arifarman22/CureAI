import re
import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from models import User, TokenBlocklist, db
from config.settings import (
    JWT_ACCESS_TOKEN_EXPIRES_MINUTES, JWT_REFRESH_TOKEN_EXPIRES_DAYS,
    MAX_LOGIN_ATTEMPTS, LOCKOUT_DURATION_MINUTES,
    MAX_NAME_LENGTH, MAX_EMAIL_LENGTH,
)

log = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


# --- Validators ---

def validate_email(email):
    if len(email) > MAX_EMAIL_LENGTH:
        return False
    return re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email) is not None


def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if len(password) > 128:
        return False, "Password must be under 128 characters"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"
    return True, ""


def sanitize_string(value, max_len):
    """Strip and truncate to prevent oversized input."""
    return value.strip()[:max_len] if value else ""


def make_tokens(user_id):
    access = create_access_token(
        identity=str(user_id),
        expires_delta=timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRES_MINUTES),
    )
    refresh = create_refresh_token(
        identity=str(user_id),
        expires_delta=timedelta(days=JWT_REFRESH_TOKEN_EXPIRES_DAYS),
    )
    return access, refresh


# --- Routes ---

@auth_bp.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json(silent=True) or {}
        name = sanitize_string(data.get("name", ""), MAX_NAME_LENGTH)
        email = sanitize_string(data.get("email", ""), MAX_EMAIL_LENGTH).lower()
        password = data.get("password", "")

        if not name or len(name) < 2:
            return jsonify({"error": "Name must be at least 2 characters"}), 400

        if not validate_email(email):
            return jsonify({"error": "Invalid email format"}), 400

        ok, msg = validate_password(password)
        if not ok:
            return jsonify({"error": msg}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email already registered"}), 409

        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        access, refresh = make_tokens(user.id)
        return jsonify({
            "message": "Registration successful",
            "access_token": access,
            "refresh_token": refresh,
            "user": user.to_dict(),
        }), 201

    except Exception as e:
        db.session.rollback()
        log.exception("Registration error")
        return jsonify({"error": "Registration failed. Please try again."}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json(silent=True) or {}
        email = sanitize_string(data.get("email", ""), MAX_EMAIL_LENGTH).lower()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        user = User.query.filter_by(email=email).first()

        if not user:
            # Don't reveal whether email exists
            return jsonify({"error": "Invalid email or password"}), 401

        # Account lockout check
        if user.is_locked:
            remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
            return jsonify({
                "error": f"Account locked due to too many failed attempts. Try again in {remaining} minutes."
            }), 429

        if not user.check_password(password):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
                user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                db.session.commit()
                return jsonify({
                    "error": f"Account locked after {MAX_LOGIN_ATTEMPTS} failed attempts. Try again in {LOCKOUT_DURATION_MINUTES} minutes."
                }), 429
            db.session.commit()
            remaining = MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
            return jsonify({"error": f"Invalid email or password. {remaining} attempts remaining."}), 401

        if not user.is_active:
            return jsonify({"error": "Account is deactivated"}), 403

        # Reset failed attempts on success
        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()

        access, refresh = make_tokens(user.id)
        return jsonify({
            "message": "Login successful",
            "access_token": access,
            "refresh_token": refresh,
            "user": user.to_dict(),
        }), 200

    except Exception as e:
        db.session.rollback()
        log.exception("Login error")
        return jsonify({"error": "Login failed. Please try again."}), 500


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    try:
        jwt_data = get_jwt()
        user_id = get_jwt_identity()

        # Check if refresh token is revoked
        if TokenBlocklist.query.filter_by(jti=jwt_data["jti"]).first():
            return jsonify({"error": "Token has been revoked", "code": "TOKEN_REVOKED"}), 401

        user = User.query.get(user_id)
        if not user or not user.is_active:
            return jsonify({"error": "Invalid session"}), 401

        access = create_access_token(
            identity=str(user_id),
            expires_delta=timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRES_MINUTES),
        )
        return jsonify({"access_token": access}), 200

    except Exception as e:
        log.exception("Token refresh error")
        return jsonify({"error": "Session refresh failed"}), 500


@auth_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    try:
        user = User.query.get(get_jwt_identity())
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"user": user.to_dict()}), 200
    except Exception as e:
        log.exception("Profile fetch error")
        return jsonify({"error": "Failed to load profile"}), 500


@auth_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    try:
        user = User.query.get(get_jwt_identity())
        if not user:
            return jsonify({"error": "User not found"}), 404

        data = request.get_json(silent=True) or {}

        name = sanitize_string(data.get("name", ""), MAX_NAME_LENGTH)
        if name and len(name) >= 2:
            user.name = name

        current_password = data.get("current_password", "")
        new_password = data.get("new_password", "")
        if new_password:
            if not current_password or not user.check_password(current_password):
                return jsonify({"error": "Current password is incorrect"}), 400
            ok, msg = validate_password(new_password)
            if not ok:
                return jsonify({"error": msg}), 400
            user.set_password(new_password)

        db.session.commit()
        return jsonify({"message": "Profile updated", "user": user.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        log.exception("Profile update error")
        return jsonify({"error": "Failed to update profile"}), 500


@auth_bp.route("/logout", methods=["POST"])
@jwt_required(verify_type=False)
def logout():
    """Revoke the current token (access or refresh) by adding its JTI to the blocklist."""
    try:
        jwt_data = get_jwt()
        jti = jwt_data["jti"]
        token_type = jwt_data["type"]
        user_id = get_jwt_identity()
        expires_at = datetime.utcfromtimestamp(jwt_data["exp"])

        blocked = TokenBlocklist(
            jti=jti,
            token_type=token_type,
            user_id=user_id,
            expires_at=expires_at,
        )
        db.session.add(blocked)
        db.session.commit()

        return jsonify({"message": "Logged out successfully"}), 200

    except Exception as e:
        db.session.rollback()
        log.exception("Logout error")
        return jsonify({"message": "Logged out"}), 200
