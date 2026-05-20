from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, flash, send_from_directory)
from flask_login import (LoginManager, UserMixin, login_user,
                         logout_user, login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, timedelta, datetime
from dotenv import load_dotenv
from urllib.parse import urlsplit, urlunsplit
import database as db
import scheduler as sched
import spaced_rep as sr
from cse_videos import CSE_VIDEO_LIBRARY
import json as json_lib
import os
import logging
import base64
import hashlib
import time
import uuid
import re

logging.basicConfig(level=logging.INFO)

load_dotenv()

PROFILE_DECORATIONS = [
    {
        "id": "night_study",
        "name": "Night Study",
        "filename": "profile-decorations/night-study-frame.png",
        "cost": 840,
        "description": "A detailed late-night study frame with lamp, notes, moon, and books.",
    },
    {
        "id": "golden_books",
        "name": "Golden Books",
        "filename": "profile-decorations/golden-books-frame.png",
        "cost": 1040,
        "description": "A premium scholar frame with gold ribbons, books, papers, and pen.",
    },
    {
        "id": "science_neon",
        "name": "Science Neon",
        "filename": "profile-decorations/science-neon-frame.png",
        "cost": 920,
        "description": "A bright STEM frame with neon science, DNA, microscope, and calculator details.",
    },
    {
        "id": "graduation_gold",
        "name": "Graduation Gold",
        "filename": "profile-decorations/graduation-gold-frame.png",
        "cost": 1000,
        "description": "A formal achievement frame with gold laurels, stars, and graduation cap.",
    },
    {
        "id": "school_supplies",
        "name": "School Supplies",
        "filename": "profile-decorations/school-supplies-frame.png",
        "cost": 360,
        "description": "A colorful everyday study frame with pencils, ruler, compass, and highlighter.",
    },
    {
        "id": "pastel_study",
        "name": "Pastel Study",
        "filename": "profile-decorations/pastel-study-frame.png",
        "cost": 720,
        "description": "An animated pastel study frame with floating books, paper plane, flowers, and stationery.",
    },
]
PROFILE_DECORATION_ASSETS = {item["id"]: item["filename"] for item in PROFILE_DECORATIONS}
PROFILE_DECORATION_REWARD_PREFIX = "avatar-decoration-"
PROFILE_MEDIA_MAX_SECONDS = 20
PROFILE_AVATAR_MEDIA_MAX_BYTES = 6 * 1024 * 1024
PROFILE_BANNER_MEDIA_MAX_BYTES = 6 * 1024 * 1024
PROFILE_MEDIA_PAYLOAD_MAX_CHARS = 4_350_000
PROFILE_AVATAR_MEDIA_MAX_MB = "6"
PROFILE_BANNER_MEDIA_MAX_MB = "6"
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "").strip().lower()
CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")
CLOUDINARY_PROFILE_FOLDER = os.environ.get("CLOUDINARY_PROFILE_FOLDER", "studyflow/profile-media")
CLOUDINARY_UPLOAD_ENABLED = bool(CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET)

_BASE = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__,
            template_folder=os.path.join(_BASE, "templates"),
            static_folder=os.path.join(_BASE, "static"))
app.secret_key = os.environ.get("SECRET_KEY", "studyflow_secret_changeme_in_prod")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


@app.route("/service-worker.js")
def service_worker():
    response = send_from_directory(app.static_folder, "service-worker.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    return response

DELIVERY_COUPONS = [
    "VEDLOVESDIYU",
    "VEDREALLYLOVESDIYU",
    "VEDHEARTU",
    "V143D",
]

AVATAR_DECORATION_REWARDS = [
    {
        "id": f"{PROFILE_DECORATION_REWARD_PREFIX}{item['id']}",
        "title": f"{item['name']} Frame",
        "cost": item["cost"],
        "description": item["description"],
        "icon": "sparkles",
        "visual": "avatar_decoration",
        "decoration": item,
        "one_time": True,
    }
    for item in PROFILE_DECORATIONS
]

REDEEM_ITEMS = [
    {
        "id": "focus-pass",
        "title": "Focus Pass",
        "cost": 120,
        "description": "Claim a guilt-free 20 minute break after a study block.",
        "icon": "coffee",
    },
    {
        "id": "theme-badge",
        "title": "Profile Glow Badge",
        "cost": 220,
        "description": "A cosmetic achievement you can show as earned.",
        "icon": "sparkles",
    },
    {
        "id": "deadline-shield",
        "title": "Deadline Shield",
        "cost": 350,
        "description": "A one-time self-approved deadline recovery token.",
        "icon": "shield-check",
    },
    {
        "id": "delivery-treat",
        "title": "Swiggy/Blinkit Treat",
        "cost": 200,
        "description": "Redeem an order coupon worth up to Rs 300 for your next snack or study refill.",
        "icon": "shopping-bag",
        "visual": "delivery",
        "coupon_codes": DELIVERY_COUPONS,
    },
    {
        "id": "deep-work",
        "title": "Deep Work Voucher",
        "cost": 500,
        "description": "Reserve a premium 90 minute deep work session reward.",
        "icon": "brain",
    },
] + AVATAR_DECORATION_REWARDS


def _is_safe_redirect_url(target):
    """Allow only relative redirects within this app."""
    if not target:
        return False
    ref_url = urlsplit(request.host_url)
    test_url = urlsplit(target)
    return not test_url.netloc or (
        test_url.scheme in ("http", "https") and test_url.netloc == ref_url.netloc
    )


def _redirect_back(default_endpoint="dashboard"):
    next_page = request.args.get("next")
    if _is_safe_redirect_url(next_page):
        return redirect(next_page)
    return redirect(url_for(default_endpoint))


def _coupon_for_redemption(user_id, reward):
    codes = reward.get("coupon_codes") or []
    if not codes:
        return ""
    claimed = db.count_reward_redemptions(user_id, reward["id"])
    return codes[claimed % len(codes)]


def _decoration_id_from_reward(reward_id):
    if not reward_id.startswith(PROFILE_DECORATION_REWARD_PREFIX):
        return ""
    decoration_id = reward_id[len(PROFILE_DECORATION_REWARD_PREFIX):]
    return decoration_id if decoration_id in PROFILE_DECORATION_ASSETS else ""


def _owned_profile_decoration_ids(user):
    if not user or not getattr(user, "is_authenticated", False):
        return set()
    if getattr(user, "is_verified", 0):
        return set(PROFILE_DECORATION_ASSETS.keys())
    reward_ids = db.get_redeemed_reward_ids(user.id)
    return {
        _decoration_id_from_reward(reward_id)
        for reward_id in reward_ids
        if _decoration_id_from_reward(reward_id)
    }


def _available_profile_decorations(user):
    owned_ids = _owned_profile_decoration_ids(user)
    return [item for item in PROFILE_DECORATIONS if item["id"] in owned_ids]


def _can_use_profile_decoration(user, decoration_id):
    if not decoration_id:
        return True
    return decoration_id in _owned_profile_decoration_ids(user)


def _owned_reward_ids(user):
    if not user or not getattr(user, "is_authenticated", False):
        return set()
    reward_ids = db.get_redeemed_reward_ids(user.id)
    if getattr(user, "is_verified", 0):
        reward_ids = set(reward_ids)
        reward_ids.update(item["id"] for item in AVATAR_DECORATION_REWARDS)
    return reward_ids


def _filter_cse_videos(query="", subject=""):
    query = (query or "").strip().lower()
    subject = (subject or "").strip()
    videos = []
    for video in _all_cse_videos():
        if subject and video["subject"] != subject:
            continue
        haystack = " ".join([
            video["title"],
            video["channel"],
            video["subject"],
            video["level"],
            " ".join(video["topics"]),
        ]).lower()
        if query and query not in haystack:
            continue
        videos.append({
            **video,
            "thumbnail": f"https://img.youtube.com/vi/{video['youtube_id']}/hqdefault.jpg",
            "embed_url": f"https://www.youtube-nocookie.com/embed/{video['youtube_id']}",
            "watch_url": f"https://www.youtube.com/watch?v={video['youtube_id']}",
        })
    return videos


def _all_cse_videos():
    hidden = db.get_hidden_cse_video_ids()
    custom = {video["youtube_id"]: video for video in db.get_cse_video_links()}
    videos = []
    for video in CSE_VIDEO_LIBRARY:
        if video["youtube_id"] in hidden:
            continue
        videos.append(custom.pop(video["youtube_id"], {**video, "source": "core"}))
    videos.extend(custom.values())
    return videos


def _extract_youtube_id(value):
    value = (value or "").strip()
    if not value:
        return ""
    patterns = [
        r"(?:v=|/embed/|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})",
        r"^([A-Za-z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            return match.group(1)
    return ""


def _format_chat_timestamp(value):
    if not value:
        return ""
    try:
        stamp = datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value
    return f"{stamp.strftime('%b')} {stamp.day}, {stamp.year}, {stamp.strftime('%I:%M %p').lstrip('0')}"


def _prepare_chat_thread_display(thread):
    previous = None
    for msg in thread:
        try:
            current = datetime.strptime((msg.get("created_at") or "")[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            current = None
        msg["time_label"] = _format_chat_timestamp(msg.get("created_at", ""))
        msg["show_time_divider"] = not previous or not current or (current - previous).total_seconds() >= 3 * 60 * 60
        if current:
            previous = current
    return thread

# ── Flask-Login setup ─────────────────────────────────────────────────────────

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access StudyFlow."
login_manager.login_message_category = "info"


class User(UserMixin):
    def __init__(self, row):
        self.id       = row["id"]
        self.username = row["username"]
        self.email    = row["email"]
        self.user_code = row.get("user_code", "")
        self.avatar_data_url = row.get("avatar_data_url", "")
        self.banner_data_url = row.get("banner_data_url", "")
        self.profile_decoration = row.get("profile_decoration", "")
        self.is_verified = row.get("is_verified", 0)
        self.moderation_status = row.get("moderation_status", "active")

    def get_id(self):
        return str(self.id)


@login_manager.user_loader
def load_user(user_id):
    row = db.get_user_by_id(int(user_id))
    return User(row) if row else None


@app.context_processor
def inject_notification_count():
    base_context = {
        "profile_decorations": PROFILE_DECORATIONS,
        "profile_decoration_assets": PROFILE_DECORATION_ASSETS,
        "available_profile_decorations": [],
        "owned_profile_decoration_ids": set(),
        "profile_media_max_seconds": PROFILE_MEDIA_MAX_SECONDS,
        "profile_avatar_media_max_bytes": PROFILE_AVATAR_MEDIA_MAX_BYTES,
        "profile_banner_media_max_bytes": PROFILE_BANNER_MEDIA_MAX_BYTES,
        "profile_media_payload_max_chars": PROFILE_MEDIA_PAYLOAD_MAX_CHARS,
        "profile_avatar_media_max_mb": PROFILE_AVATAR_MEDIA_MAX_MB,
        "profile_banner_media_max_mb": PROFILE_BANNER_MEDIA_MAX_MB,
        "cloudinary_upload_enabled": CLOUDINARY_UPLOAD_ENABLED,
        "is_profile_video_media": _is_profile_video_media,
        "is_profile_gif_media": _is_profile_gif_media,
        "profile_banner_media_url": _profile_banner_media_url,
        "profile_avatar_poster_url": _profile_avatar_poster_url,
        "profile_banner_poster_url": _profile_banner_poster_url,
        "user_is_online": db.is_user_online,
    }
    if current_user.is_authenticated:
        try:
            owned_profile_decoration_ids = _owned_profile_decoration_ids(current_user)
            return {
                **base_context,
                "available_profile_decorations": [
                    item for item in PROFILE_DECORATIONS if item["id"] in owned_profile_decoration_ids
                ],
                "owned_profile_decoration_ids": owned_profile_decoration_ids,
                "notification_count": db.get_notification_count(current_user.id),
                "unread_message_count": db.get_unread_message_count(current_user.id),
                "flowcoin_balance": db.get_flowcoin_balance(current_user.id),
            }
        except Exception:
            return {**base_context, "notification_count": 0, "unread_message_count": 0, "flowcoin_balance": 0}
    return {**base_context, "notification_count": 0, "unread_message_count": 0, "flowcoin_balance": 0}


@app.before_request
def enforce_account_status():
    if not current_user.is_authenticated:
        return None
    if request.endpoint in {"static", "logout"}:
        return None
    if getattr(current_user, "moderation_status", "active") in {"suspended", "banned"}:
        status = current_user.moderation_status
        logout_user()
        flash(f"Your account is {status}. Contact support if this looks wrong.", "error")
        return redirect(url_for("login"))
    if current_user.profile_decoration and not _can_use_profile_decoration(current_user, current_user.profile_decoration):
        db.update_profile_decoration(current_user.id, "")
        row = db.get_user_by_id(current_user.id)
        login_user(User(row), remember=True)
    db.touch_presence(current_user.id)
    return None


# Initialise DB on first run
with app.app_context():
    try:
        db.init_db()
        logging.info(f"Database initialised at: {db.DB_PATH}")
    except Exception as e:
        logging.error(f"Database init failed: {e}", exc_info=True)


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

        error = None
        if not username or not email or not password:
            error = "All fields are required."
        elif len(username) < 3:
            error = "Username must be at least 3 characters."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif password != confirm:
            error = "Passwords do not match."
        elif db.get_user_by_username(username):
            error = "That username is already taken."
        elif db.get_user_by_email(email):
            error = "An account with that email already exists."

        if error:
            flash(error, "error")
            return render_template("register.html",
                                   username=username, email=email)

        pw_hash = generate_password_hash(password)
        uid = db.create_user(username, email, pw_hash)
        row = db.get_user_by_id(uid)
        login_user(User(row), remember=True)
        flash(f"Welcome to StudyFlow, {username}! 🎉", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html", username="", email="")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password   = request.form.get("password", "")
        remember   = bool(request.form.get("remember"))

        # Allow login by username OR email
        row = db.get_user_by_username(identifier) or db.get_user_by_email(identifier)
        if row and row.get("moderation_status", "active") in {"suspended", "banned"}:
            flash(f"This account is {row['moderation_status']}. Contact support if this looks wrong.", "error")
            return render_template("login.html", identifier=identifier)
        if row and check_password_hash(row["password_hash"], password):
            login_user(User(row), remember=remember)
            flash(f"Welcome back, {row['username']}! 👋", "success")
            return _redirect_back("dashboard")

        flash("Incorrect username/email or password.", "error")
    return render_template("login.html", identifier="")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been logged out. See you soon! 👋", "info")
    return redirect(url_for("login"))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    uid = current_user.id
    stats   = db.get_dashboard_stats(uid)
    subjects = db.get_all_subjects(uid)
    streak  = db.get_streak(uid)
    weekly  = db.get_weekly_report(uid)
    return render_template("dashboard.html",
                           stats=stats, subjects=subjects,
                           streak=streak, weekly=weekly,
                           today_date=date.today(),
                           today=date.today().isoformat(),
                           timedelta=timedelta)
# Social / People

@app.route("/people")
@login_required
def people():
    query = request.args.get("q", "").strip()
    results = db.search_users(query, current_user.id) if query else []
    following = db.get_following(current_user.id)
    followers = db.get_followers(current_user.id)
    return render_template("people.html",
                           query=query,
                           results=results,
                           following=following,
                           followers=followers)


def _profile_response(profile):
    if not profile:
        flash("User not found.", "error")
        return redirect(url_for("people"))
    return render_template("profile.html", profile=profile)


def _clean_uploaded_data_url(value, max_bytes, label):
    value = (value or "").strip()
    if not value:
        return ""
    if not value.startswith("data:image/") or ";base64," not in value:
        raise ValueError(f"{label} must be a cropped image.")
    header, encoded = value.split(",", 1)
    content_type = header[5:].split(";", 1)[0].lower()
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError(f"{label} must be JPG, PNG, or WebP.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError(f"{label} could not be read.") from exc
    if len(raw) > max_bytes:
        raise ValueError(f"{label} is too large after cropping.")
    return f"data:{content_type};base64,{encoded}"


def _is_animated_profile_media(content_type):
    return content_type == "image/gif" or content_type.startswith("video/")


def _is_cloudinary_media_url(value):
    value = (value or "").strip()
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if parsed.scheme != "https" or parsed.netloc.lower() != "res.cloudinary.com":
        return False
    if not CLOUDINARY_CLOUD_NAME:
        return True
    cloud = parsed.path.strip("/").split("/", 1)[0]
    return cloud.lower() == CLOUDINARY_CLOUD_NAME.lower()


def _is_profile_video_media(value):
    value = (value or "").strip()
    if value.startswith("data:video/"):
        return True
    if not _is_cloudinary_media_url(value):
        return False
    return "/video/upload/" in urlsplit(value).path


def _is_profile_gif_media(value):
    value = (value or "").strip()
    if value.startswith("data:image/gif"):
        return True
    if not _is_cloudinary_media_url(value):
        return False
    return urlsplit(value).path.lower().split("?", 1)[0].endswith(".gif")


def _cloudinary_signature(params):
    payload = "&".join(f"{key}={params[key]}" for key in sorted(params) if params[key] not in (None, ""))
    return hashlib.sha1(f"{payload}{CLOUDINARY_API_SECRET}".encode("utf-8")).hexdigest()


def _cloudinary_transformed_url(value, transformation):
    value = (value or "").strip()
    if not transformation or not _is_cloudinary_media_url(value):
        return value
    parsed = urlsplit(value)
    if "/upload/" not in parsed.path:
        return value
    before, after = parsed.path.split("/upload/", 1)
    if after.startswith(f"{transformation}/"):
        return value
    return urlunsplit((
        parsed.scheme,
        parsed.netloc,
        f"{before}/upload/{transformation}/{after}",
        parsed.query,
        parsed.fragment,
    ))


def _profile_banner_media_url(value):
    if _is_profile_video_media(value):
        return value
    return _cloudinary_transformed_url(value, "c_fill,g_auto,w_1800,h_300,q_auto")


def _profile_avatar_poster_url(value):
    if not (_is_profile_video_media(value) or _is_profile_gif_media(value)) or not _is_cloudinary_media_url(value):
        return ""
    poster_url = _cloudinary_transformed_url(value, "c_fill,g_auto,w_500,h_500,q_auto,so_0")
    parsed = urlsplit(poster_url)
    path = re.sub(r"\.(mp4|webm|mov|gif)$", ".jpg", parsed.path, flags=re.IGNORECASE)
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def _profile_banner_poster_url(value):
    if not (_is_profile_video_media(value) or _is_profile_gif_media(value)) or not _is_cloudinary_media_url(value):
        return ""
    poster_url = _cloudinary_transformed_url(value, "c_fill,g_center,w_1800,h_300,q_auto,so_0")
    parsed = urlsplit(poster_url)
    path = re.sub(r"\.(mp4|webm|mov|gif)$", ".jpg", parsed.path, flags=re.IGNORECASE)
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def _gif_duration_seconds(raw):
    total = 0
    index = 0
    while True:
        index = raw.find(b"\x21\xf9\x04", index)
        if index == -1 or index + 8 > len(raw):
            break
        delay = int.from_bytes(raw[index + 4:index + 6], "little")
        total += delay or 10
        index += 8
    return total / 100 if total else 0


def _clean_profile_media_data_url(value, max_bytes, label, allow_animated=False, duration_seconds=None):
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith("https://"):
        if not _is_cloudinary_media_url(value):
            raise ValueError(f"{label} must be uploaded through StudyFlow media storage.")
        if (_is_profile_video_media(value) or _is_profile_gif_media(value)) and not allow_animated:
            raise ValueError(f"Animated {label.lower()} media is only available to verified accounts.")
        return value
    if ";base64," not in value or not value.startswith("data:"):
        raise ValueError(f"{label} could not be read.")
    if len(value) > PROFILE_MEDIA_PAYLOAD_MAX_CHARS:
        raise ValueError(f"{label} is too large for the current deployment limit.")
    header, encoded = value.split(",", 1)
    content_type = header[5:].split(";", 1)[0].lower()
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif", "video/mp4", "video/webm", "video/quicktime"}
    if content_type not in allowed_types:
        media_hint = "JPG, PNG, WebP, GIF, MP4, WebM, or MOV" if allow_animated else "JPG, PNG, or WebP"
        raise ValueError(f"{label} must be {media_hint}.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError(f"{label} could not be read.") from exc
    if len(raw) > max_bytes:
        raise ValueError(f"{label} is too large.")
    if _is_animated_profile_media(content_type) and not allow_animated:
        raise ValueError(f"Animated {label.lower()} media is only available to verified accounts.")
    if content_type == "image/gif":
        gif_seconds = _gif_duration_seconds(raw)
        if gif_seconds and gif_seconds > PROFILE_MEDIA_MAX_SECONDS:
            raise ValueError(f"{label} GIF must be {PROFILE_MEDIA_MAX_SECONDS} seconds or shorter.")
    if content_type.startswith("video/"):
        try:
            seconds = float(duration_seconds or 0)
        except (TypeError, ValueError):
            seconds = 0
        if seconds <= 0:
            raise ValueError(f"{label} video duration could not be verified.")
        if seconds > PROFILE_MEDIA_MAX_SECONDS:
            raise ValueError(f"{label} video must be {PROFILE_MEDIA_MAX_SECONDS} seconds or shorter.")
    return f"data:{content_type};base64,{encoded}"


def _creator_required():
    if not getattr(current_user, "is_verified", 0):
        flash("This section is only available to StudyFlow creators.", "error")
        return False
    return True


def _log_creator_action(action, target_type="", target_id="", detail=""):
    try:
        db.log_admin_audit(current_user.id, action, target_type, target_id, detail)
    except Exception:
        logging.exception("Failed to write admin audit log")


@app.route("/users/user/<int:user_id>")
@login_required
def user_profile_by_id(user_id):
    return _profile_response(db.get_public_profile_by_id(user_id, current_user.id))


@app.route("/users/<username>")
@login_required
def user_profile(username):
    return _profile_response(db.get_public_profile(username, current_user.id))


@app.route("/users/user/<int:user_id>/<kind>")
@login_required
def user_connections(user_id, kind):
    if kind not in {"followers", "following"}:
        return redirect(url_for("user_profile_by_id", user_id=user_id))
    profile = db.get_public_profile_by_id(user_id, current_user.id)
    if not profile:
        flash("User not found.", "error")
        return redirect(url_for("people"))
    if not profile["can_view_connections"]:
        flash("Only followers can view this list.", "error")
        return redirect(url_for("user_profile_by_id", user_id=user_id))
    people = db.get_followers(user_id) if kind == "followers" else db.get_following(user_id)
    return render_template("connections.html", profile=profile, people=people, kind=kind)


@app.route("/creator/admin")
@login_required
def admin_dashboard():
    if not _creator_required():
        return redirect(url_for("dashboard"))
    _log_creator_action("view_admin_dashboard", "page", "creator/admin", request.path)
    return render_template(
        "admin_dashboard.html",
        summary=db.get_admin_summary(),
        recent_users=db.get_recent_users(),
        tickets=db.get_support_tickets(limit=5),
        audit_logs=db.get_audit_logs(limit=6),
        cse_videos=_filter_cse_videos(),
    )


@app.route("/creator/support", methods=["GET", "POST"])
@login_required
def support_inbox():
    if not _creator_required():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        try:
            ticket_id = int(request.form.get("ticket_id", 0))
        except ValueError:
            ticket_id = 0
        status = request.form.get("status", "open")
        if status in {"open", "reviewing", "resolved"} and ticket_id:
            db.update_support_ticket_status(ticket_id, status)
            _log_creator_action("update_support_ticket", "support_ticket", ticket_id, f"status={status}")
            flash("Support ticket updated.", "success")
        return redirect(url_for("support_inbox"))
    _log_creator_action("view_support_inbox", "page", "creator/support", request.path)
    return render_template("support_inbox.html", tickets=db.get_support_tickets())


@app.route("/creator/audit")
@login_required
def audit_logs():
    if not _creator_required():
        return redirect(url_for("dashboard"))
    _log_creator_action("view_audit_logs", "page", "creator/audit", request.path)
    return render_template("audit_logs.html", audit_logs=db.get_audit_logs())


@app.route("/creator/users/<int:user_id>/moderation", methods=["POST"])
@login_required
def moderate_user(user_id):
    if not _creator_required():
        return redirect(url_for("dashboard"))
    target = db.get_user_by_id(user_id)
    if not target:
        flash("User not found.", "error")
        return redirect(url_for("people"))
    if target.get("is_verified") or target["id"] == current_user.id:
        flash("Creator accounts cannot be moderated from this menu.", "error")
        return redirect(url_for("user_profile_by_id", user_id=user_id))
    action = request.form.get("action", "suspend")
    status = "banned" if action == "ban" else "suspended"
    reason = request.form.get("reason", "").strip() or f"Account {status} by creator"
    db.update_user_moderation_status(user_id, status)
    _log_creator_action(status, "user", user_id, reason)
    flash(f"{target['username']} has been {status}.", "success")
    return redirect(url_for("user_profile_by_id", user_id=user_id))


@app.route("/creator/users/<int:user_id>/flowcoins", methods=["POST"])
@login_required
def creator_adjust_flowcoins(user_id):
    if not _creator_required():
        return redirect(url_for("dashboard"))
    target = db.get_user_by_id(user_id)
    if not target:
        flash("User not found.", "error")
        return redirect(url_for("people"))
    if target.get("is_verified") or target["id"] == current_user.id:
        flash("Creator account FlowCoins cannot be changed from this menu.", "error")
        return redirect(url_for("user_profile_by_id", user_id=user_id))
    try:
        amount = int(request.form.get("amount", 0))
    except ValueError:
        amount = 0
    reason = request.form.get("reason", "").strip()
    if not amount or not reason:
        flash("Add an amount and reason for the FlowCoin adjustment.", "error")
        return redirect(url_for("user_profile_by_id", user_id=user_id))
    db.adjust_flowcoins(
        user_id,
        amount,
        f"Creator adjustment: {reason}",
        f"creator_adjust:{current_user.id}:{user_id}:{uuid.uuid4().hex}",
    )
    _log_creator_action("adjust_flowcoins", "user", user_id, f"{amount}: {reason}")
    flash(f"FlowCoins updated for {target['username']}.", "success")
    return redirect(url_for("user_profile_by_id", user_id=user_id))


@app.route("/creator/videos", methods=["POST"])
@login_required
def creator_add_video():
    if not _creator_required():
        return redirect(url_for("dashboard"))
    youtube_id = _extract_youtube_id(request.form.get("youtube_url", ""))
    title = request.form.get("title", "").strip()
    subject = request.form.get("subject", "").strip()
    channel = request.form.get("channel", "").strip() or "YouTube"
    duration = request.form.get("duration", "").strip()
    level = request.form.get("level", "Beginner").strip() or "Beginner"
    topics = [topic.strip() for topic in request.form.get("topics", "").split(",") if topic.strip()]
    if not youtube_id or not title or not subject:
        flash("Add a valid YouTube link, title, and subject.", "error")
        return redirect(url_for("admin_dashboard"))
    db.add_cse_video_link(youtube_id, title, channel, subject, duration, level, topics, current_user.id)
    _log_creator_action("add_cse_video", "video", youtube_id, title)
    flash("CSE video added to the library.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/creator/videos/<youtube_id>/remove", methods=["POST"])
@login_required
def creator_remove_video(youtube_id):
    if not _creator_required():
        return redirect(url_for("dashboard"))
    removed_type = db.remove_cse_video_link(youtube_id, current_user.id)
    _log_creator_action("remove_cse_video", "video", youtube_id, removed_type)
    flash("CSE video removed from the library.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/creator/videos/<youtube_id>/update", methods=["POST"])
@login_required
def creator_update_video(youtube_id):
    if not _creator_required():
        return redirect(url_for("dashboard"))
    title = request.form.get("title", "").strip()
    subject = request.form.get("subject", "").strip()
    channel = request.form.get("channel", "").strip() or "YouTube"
    duration = request.form.get("duration", "").strip()
    level = request.form.get("level", "Beginner").strip() or "Beginner"
    topics = [topic.strip() for topic in request.form.get("topics", "").split(",") if topic.strip()]
    if not title or not subject:
        flash("Video title and subject are required.", "error")
        return redirect(url_for("admin_dashboard"))
    db.add_cse_video_link(youtube_id, title, channel, subject, duration, level, topics, current_user.id)
    _log_creator_action("update_cse_video", "video", youtube_id, title)
    flash("CSE video details updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/users/<int:user_id>/follow", methods=["POST"])
@login_required
def follow_user(user_id):
    if user_id == current_user.id:
        flash("You cannot follow yourself.", "error")
        return redirect(url_for("people"))
    target = db.get_user_by_id(user_id)
    if not target:
        flash("User not found.", "error")
        return redirect(url_for("people"))
    db.follow_user(current_user.id, user_id)
    flash(f"You are now following {target['username']}.", "success")
    next_page = request.form.get("next")
    if _is_safe_redirect_url(next_page):
        return redirect(next_page)
    return redirect(url_for("user_profile_by_id", user_id=target["id"]))


@app.route("/users/<int:user_id>/unfollow", methods=["POST"])
@login_required
def unfollow_user(user_id):
    target = db.get_user_by_id(user_id)
    if not target:
        flash("User not found.", "error")
        return redirect(url_for("people"))
    db.unfollow_user(current_user.id, user_id)
    flash(f"You unfollowed {target['username']}.", "info")
    next_page = request.form.get("next")
    if _is_safe_redirect_url(next_page):
        return redirect(next_page)
    return redirect(url_for("user_profile_by_id", user_id=target["id"]))


# ── Subjects ──────────────────────────────────────────────────────────────────

@app.route("/messages")
@login_required
def messages():
    conversations = db.get_conversations(current_user.id)
    return render_template(
        "messages.html",
        conversations=conversations,
        other=None,
        thread=[],
        disappearing={"enabled": False, "hours": 0},
    )


def _conversation_response(other):
    if not other:
        flash("User not found.", "error")
        return redirect(url_for("messages"))
    if other["id"] == current_user.id:
        flash("You cannot message yourself.", "error")
        return redirect(url_for("messages"))

    if request.method == "POST":
        body = request.form.get("body", "").strip()
        try:
            reply_to_message_id = int(request.form.get("reply_to_message_id") or 0) or None
        except ValueError:
            reply_to_message_id = None
        if not body:
            flash("Message cannot be empty.", "error")
        else:
            db.send_message(current_user.id, other["id"], body, reply_to_message_id=reply_to_message_id)
        return redirect(url_for("conversation_by_user_id", user_id=other["id"]))

    thread = _prepare_chat_thread_display(db.get_message_thread(current_user.id, other["id"]))
    db.mark_thread_read(current_user.id, other["id"])
    disappearing = db.get_disappearing_mode(current_user.id, other["id"])
    conversations = db.get_conversations(current_user.id)
    return render_template(
        "messages.html",
        conversations=conversations,
        other=other,
        thread=thread,
        disappearing=disappearing,
    )


@app.route("/messages/user/<int:user_id>", methods=["GET", "POST"])
@login_required
def conversation_by_user_id(user_id):
    return _conversation_response(db.get_user_by_id(user_id))


@app.route("/messages/<username>", methods=["GET", "POST"])
@login_required
def conversation(username):
    other = db.get_user_by_username(username) or db.get_user_by_username_loose(username)
    return _conversation_response(other)


def _message_thread_response(other):
    if not other or other["id"] == current_user.id:
        return jsonify({"error": "not found"}), 404
    thread = db.get_message_thread(current_user.id, other["id"])
    if request.args.get("mark_read") == "1":
        db.mark_thread_read(current_user.id, other["id"])
        thread = db.get_message_thread(current_user.id, other["id"])
    return jsonify({
        "disappearing": db.get_disappearing_mode(current_user.id, other["id"]),
        "other_typing": db.is_user_typing(other["id"], current_user.id),
        "other_online": db.is_user_online(other["id"]),
        "messages": [
            {
                "id": msg["id"],
                "sender_id": msg["sender_id"],
                "receiver_id": msg["receiver_id"],
                "body": msg["body"],
                "attachment_name": msg.get("attachment_name", ""),
                "attachment_type": msg.get("attachment_type", ""),
                "attachment_data_url": msg.get("attachment_data_url", ""),
                "created_at": msg["created_at"],
                "edited_at": msg.get("edited_at", ""),
                "read_at": msg.get("read_at", ""),
                "reply_to": msg.get("reply_to"),
                "reactions": msg.get("reactions", []),
                "is_mine": msg["sender_id"] == current_user.id,
                "can_edit": msg["sender_id"] == current_user.id,
            }
            for msg in thread
        ]
    })


@app.route("/api/messages/user/<int:user_id>")
@login_required
def api_message_thread_by_user_id(user_id):
    return _message_thread_response(db.get_user_by_id(user_id))


@app.route("/api/messages/<username>")
@login_required
def api_message_thread(username):
    other = db.get_user_by_username(username) or db.get_user_by_username_loose(username)
    return _message_thread_response(other)


def _send_message_response(other):
    if not other or other["id"] == current_user.id:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()
    attachment = data.get("attachment") or {}
    reply_to_message_id = data.get("reply_to_message_id")
    try:
        reply_to_message_id = int(reply_to_message_id) if reply_to_message_id else None
    except (TypeError, ValueError):
        reply_to_message_id = None
    if not isinstance(attachment, dict):
        attachment = {}
    if not body and not attachment.get("data_url"):
        return jsonify({"error": "Message cannot be empty."}), 400
    if attachment.get("data_url") and len(attachment.get("data_url", "")) > 2_000_000:
        return jsonify({"error": "Attachment is too large."}), 400
    msg_id = db.send_message(current_user.id, other["id"], body, attachment, reply_to_message_id)
    return jsonify({"status": "sent", "id": msg_id})


@app.route("/api/messages/user/<int:user_id>/send", methods=["POST"])
@login_required
def api_send_message_by_user_id(user_id):
    return _send_message_response(db.get_user_by_id(user_id))


@app.route("/api/messages/<username>/send", methods=["POST"])
@login_required
def api_send_message(username):
    other = db.get_user_by_username(username) or db.get_user_by_username_loose(username)
    return _send_message_response(other)


@app.route("/api/presence/ping", methods=["POST"])
@login_required
def api_presence_ping():
    db.touch_presence(current_user.id)
    return jsonify({"status": "online"})


@app.route("/api/messages/summary")
@login_required
def api_message_summaries():
    return jsonify({
        "conversations": [
            {
                "user_id": item["user_id"],
                "is_typing": item["is_typing"],
                "is_online": item["is_online"],
                "unread": item["unread"],
                "last": item["last"],
            }
            for item in db.get_conversation_summaries(current_user.id)
        ]
    })


@app.route("/api/messages/user/<int:user_id>/typing", methods=["POST"])
@login_required
def api_set_typing(user_id):
    other = db.get_user_by_id(user_id)
    if not other or other["id"] == current_user.id:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    db.set_typing_status(current_user.id, other["id"], bool(data.get("typing")))
    return jsonify({"status": "ok"})


@app.route("/api/messages/<int:message_id>", methods=["PATCH"])
@login_required
def api_edit_message(message_id):
    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "Message cannot be empty."}), 400
    if not db.edit_message(message_id, current_user.id, body):
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "edited"})


@app.route("/api/messages/<int:message_id>", methods=["DELETE"])
@login_required
def api_delete_message(message_id):
    if not db.delete_message(message_id, current_user.id):
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "deleted"})


@app.route("/api/messages/<int:message_id>/reaction", methods=["POST"])
@login_required
def api_react_to_message(message_id):
    data = request.get_json(silent=True) or {}
    emoji = (data.get("emoji") or "").strip()
    if not emoji:
        return jsonify({"error": "Emoji is required."}), 400
    if not db.react_to_message(message_id, current_user.id, emoji):
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "reacted"})


@app.route("/api/messages/user/<int:user_id>/disappearing", methods=["POST"])
@login_required
def api_set_disappearing_mode(user_id):
    other = db.get_user_by_id(user_id)
    if not other or other["id"] == current_user.id:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    mode = db.set_disappearing_mode(
        current_user.id,
        other["id"],
        bool(data.get("enabled")),
    )
    return jsonify({"status": "updated", "disappearing": mode})


def _public_call(call):
    if not call:
        return None
    peer = call.get("peer") or {}
    return {
        "id": call["id"],
        "kind": call["kind"],
        "status": call["status"],
        "created_at": call["created_at"],
        "answered_at": call.get("answered_at", ""),
        "ended_at": call.get("ended_at", ""),
        "is_caller": call["is_caller"],
        "peer": {
            "id": peer.get("id"),
            "username": peer.get("username", "Unknown"),
            "avatar_data_url": peer.get("avatar_data_url", ""),
            "profile_decoration": peer.get("profile_decoration", ""),
        },
    }


@app.route("/api/calls/start/<int:user_id>", methods=["POST"])
@login_required
def api_start_call(user_id):
    other = db.get_user_by_id(user_id)
    if not other or other["id"] == current_user.id:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    kind = data.get("kind", "video")
    if kind not in ("voice", "video"):
        kind = "video"
    call = db.create_call(uuid.uuid4().hex, current_user.id, other["id"], kind)
    return jsonify({"call": _public_call(call)})


@app.route("/api/calls")
@login_required
def api_calls():
    return jsonify({
        "calls": [_public_call(call) for call in db.get_active_calls(current_user.id)]
    })


@app.route("/api/calls/<call_id>/<action>", methods=["POST"])
@login_required
def api_call_action(call_id, action):
    if action not in ("accept", "decline", "end"):
        return jsonify({"error": "bad action"}), 400
    status = "active" if action == "accept" else "declined" if action == "decline" else "ended"
    call = db.update_call_status(call_id, current_user.id, status)
    if not call:
        return jsonify({"error": "not found"}), 404
    return jsonify({"call": _public_call(call)})


@app.route("/api/calls/<call_id>/signals", methods=["GET", "POST"])
@login_required
def api_call_signals(call_id):
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        signal_type = data.get("type", "")
        payload = data.get("payload")
        if signal_type not in ("offer", "answer", "ice") or payload is None:
            return jsonify({"error": "bad signal"}), 400
        ok = db.add_call_signal(
            call_id,
            current_user.id,
            signal_type,
            json_lib.dumps(payload),
        )
        if not ok:
            return jsonify({"error": "not found"}), 404
        return jsonify({"status": "sent"})

    after = request.args.get("after", "0")
    try:
        after_id = int(after)
    except ValueError:
        after_id = 0
    rows = db.get_call_signals(call_id, current_user.id, after_id)
    return jsonify({
        "signals": [
            {
                "id": row["id"],
                "sender_id": row["sender_id"],
                "type": row["signal_type"],
                "payload": json_lib.loads(row["payload"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    })


@app.route("/notifications")
@login_required
def notifications():
    items = db.get_notifications(current_user.id)
    follower_keys = [item.get("key") for item in items if item.get("type") == "follower"]
    if follower_keys:
        db.mark_notifications_read(current_user.id, follower_keys)
        items = db.get_notifications(current_user.id)
    return render_template("notifications.html", notifications=items)


@app.route("/videos")
@login_required
def video_library():
    query = request.args.get("q", "")
    subject = request.args.get("subject", "")
    videos = _filter_cse_videos(query, subject)
    all_videos = _all_cse_videos()
    subjects = sorted({video["subject"] for video in all_videos})
    return render_template(
        "videos.html",
        videos=videos,
        featured=videos[0] if videos else None,
        query=query,
        current_subject=subject,
        subjects=subjects,
        total_videos=len(all_videos),
    )


@app.route("/redeem")
@login_required
def redeem():
    owned_reward_ids = _owned_reward_ids(current_user)
    return render_template(
        "redeem.html",
        rewards=REDEEM_ITEMS,
        balance=db.get_flowcoin_balance(current_user.id),
        owned_reward_ids=owned_reward_ids,
        activity=db.get_flowcoin_activity(current_user.id),
        redemptions=db.get_redemptions(current_user.id),
    )


@app.route("/redeem/<reward_id>", methods=["POST"])
@login_required
def redeem_reward(reward_id):
    reward = next((item for item in REDEEM_ITEMS if item["id"] == reward_id), None)
    if not reward:
        flash("Reward not found.", "error")
        return redirect(url_for("redeem"))
    owned_reward_ids = _owned_reward_ids(current_user)
    if reward.get("one_time") and reward["id"] in owned_reward_ids:
        flash(f"You already own {reward['title']}.", "info")
        return redirect(url_for("redeem"))
    coupon_code = _coupon_for_redemption(current_user.id, reward)
    ok, balance = db.redeem_flowcoin_reward(
        current_user.id,
        reward["id"],
        reward["title"],
        reward["cost"],
        coupon_code,
    )
    if ok:
        decoration_id = reward.get("decoration", {}).get("id") if reward.get("visual") == "avatar_decoration" else ""
        if decoration_id:
            db.update_profile_decoration(current_user.id, decoration_id)
            row = db.get_user_by_id(current_user.id)
            login_user(User(row), remember=True)
            flash(f"Unlocked and equipped {reward['title']} for {reward['cost']} FlowCoins.", "success")
            return redirect(url_for("redeem"))
        if coupon_code:
            flash(f"Redeemed {reward['title']} for {reward['cost']} FlowCoins. Coupon: {coupon_code}", "success")
        else:
            flash(f"Redeemed {reward['title']} for {reward['cost']} FlowCoins.", "success")
    else:
        flash(f"You need {reward['cost'] - balance} more FlowCoins for that reward.", "error")
    return redirect(url_for("redeem"))


@app.route("/api/notifications/count")
@login_required
def api_notification_count():
    notification_count = db.get_notification_count(current_user.id)
    unread_messages = db.get_unread_message_count(current_user.id)
    return jsonify({
        "count": notification_count,
        "unread_messages": unread_messages,
        "sound_count": notification_count + unread_messages,
    })


@app.route("/subjects")
@login_required
def subjects():
    return render_template("subjects.html",
                           subjects=db.get_all_subjects(current_user.id))


@app.route("/subjects/add", methods=["POST"])
@login_required
def add_subject():
    name  = request.form.get("name", "").strip()
    color = request.form.get("color", "#6366f1")
    if not name:
        flash("Subject name cannot be empty.", "error")
    else:
        try:
            db.add_subject(current_user.id, name, color)
            flash(f'Subject "{name}" added!', "success")
        except Exception:
            flash("Error: that subject name already exists.", "error")
    return redirect(url_for("subjects"))


@app.route("/subjects/<int:subject_id>/delete", methods=["POST"])
@login_required
def delete_subject(subject_id):
    db.delete_subject(subject_id, current_user.id)
    flash("Subject deleted.", "info")
    return redirect(url_for("subjects"))


# ── Topics ────────────────────────────────────────────────────────────────────

@app.route("/subjects/<int:subject_id>/topics")
@login_required
def topics(subject_id):
    uid = current_user.id
    all_subjects = db.get_all_subjects(uid)
    subject = next((s for s in all_subjects if s["id"] == subject_id), None)
    if not subject:
        flash("Subject not found.", "error")
        return redirect(url_for("subjects"))
    topic_list = db.get_topics_by_subject(subject_id, uid)
    return render_template("topics.html",
                           subject=subject, topics=topic_list,
                           today=date.today().isoformat())


@app.route("/subjects/<int:subject_id>/topics/add", methods=["POST"])
@login_required
def add_topic(subject_id):
    name            = request.form.get("name", "").strip()
    deadline        = request.form.get("deadline", "")
    difficulty      = int(request.form.get("difficulty", 3))
    estimated_hours = float(request.form.get("estimated_hours", 2))
    daily_hours     = float(request.form.get("daily_hours", 4))
    if not name or not deadline:
        flash("Name and deadline are required.", "error")
    else:
        db.add_topic(subject_id, name, deadline, difficulty, estimated_hours, daily_hours)
        flash(f'Topic "{name}" added!', "success")
    return redirect(url_for("topics", subject_id=subject_id))


@app.route("/topics/<int:topic_id>/toggle", methods=["POST"])
@login_required
def toggle_topic(topic_id):
    uid = current_user.id
    all_topics = db.get_all_topics(uid)
    topic = next((t for t in all_topics if t["id"] == topic_id), None)
    db.toggle_topic_complete(topic_id, uid)
    # Check new state
    all_topics2 = db.get_all_topics(uid)
    topic2 = next((t for t in all_topics2 if t["id"] == topic_id), None)

    if topic2 and topic2["is_completed"] and topic:
        # Log streak
        db.log_topic_completion(topic_id, topic["subject_id"], uid)
        flowcoins = db.award_topic_flowcoins(uid, topic)
        streak_bonus = db.award_streak_flowcoins(uid)

        # ── Step 14: SM-2 spaced repetition ──────────────
        existing = db.get_review(topic_id, uid)
        if existing:
            n, easiness, interval = (existing["n"], existing["easiness"],
                                     existing["interval_days"])
        else:
            n, easiness, interval = 0, 2.5, 1

        quality = sr.quality_from_difficulty(topic["difficulty"])
        new_n, new_ease, new_interval, next_review = sr.sm2_next(
            n, easiness, interval, quality
        )
        db.upsert_review(topic_id, uid, new_n, new_ease,
                         new_interval, next_review, quality)

        return jsonify({
            "status": "ok",
            "review_scheduled": next_review.isoformat(),
            "interval_days": new_interval,
            "flowcoins": flowcoins,
            "streak_bonus": streak_bonus,
            "balance": db.get_flowcoin_balance(uid),
        })

    return jsonify({"status": "ok"})


@app.route("/topics/<int:topic_id>/delete", methods=["POST"])
@login_required
def delete_topic(topic_id):
    uid = current_user.id
    all_topics = db.get_all_topics(uid)
    topic = next((t for t in all_topics if t["id"] == topic_id), None)
    subject_id = topic["subject_id"] if topic else None
    db.delete_topic(topic_id, uid)
    flash("Topic deleted.", "info")
    return redirect(url_for("topics", subject_id=subject_id) if subject_id else url_for("subjects"))


@app.route("/topics/<int:topic_id>/notes", methods=["GET", "POST"])
@login_required
def topic_notes(topic_id):
    uid = current_user.id
    if request.method == "GET":
        all_topics = db.get_all_topics(uid)
        topic = next((t for t in all_topics if t["id"] == topic_id), None)
        if not topic:
            return jsonify({"error": "not found"}), 404
        return jsonify({
            "notes": topic.get("notes", ""),
            "links": json_lib.loads(topic.get("links", "[]") or "[]")
        })
    else:
        data  = request.get_json(force=True)
        notes = (data.get("notes") or "").strip()
        links = [str(l).strip() for l in (data.get("links") or []) if str(l).strip()]
        db.update_topic_notes_links(topic_id, notes, json_lib.dumps(links), uid)
        return jsonify({"status": "saved"})


# ── Schedule ──────────────────────────────────────────────────────────────────

@app.route("/schedule")
@login_required
def schedule():
    from collections import defaultdict
    uid = current_user.id

    # ── Step 13: Adaptive Rescheduling ───────────────────
    # If any incomplete session is in the past, silently regenerate.
    if db.has_stale_schedule(uid):
        all_topics  = db.get_all_topics(uid)
        prefs       = db.get_preferences(uid)
        daily_hours = prefs.get("daily_hours_default", 4.0)
        new_entries = sched.generate_schedule(all_topics, daily_hours,
                                              today=date.today())
        # Merge in any future review entries already scheduled
        reviews_due = db.get_due_reviews(uid)
        review_entries = _reviews_to_schedule_entries(reviews_due, daily_hours)
        db.save_schedule(new_entries + review_entries, uid)
        flash("📅 Your schedule was automatically updated — missed sessions rescheduled.", "info")

    entries = db.get_schedule(uid)
    grouped = defaultdict(list)
    for e in entries:
        grouped[e["date"]].append(e)
    grouped_sorted = sorted(grouped.items())

    # Due reviews badge count for the schedule page
    due_reviews = db.get_due_reviews(uid)

    return render_template("schedule.html",
                           grouped_schedule=grouped_sorted,
                           today=date.today().isoformat(),
                           due_reviews_count=len(due_reviews))


@app.route("/schedule/generate", methods=["POST"])
@login_required
def generate_schedule():
    uid = current_user.id
    all_topics = db.get_all_topics(uid)
    if not all_topics:
        flash("No topics found. Add topics first.", "error")
        return redirect(url_for("schedule"))
    prefs       = db.get_preferences(uid)
    daily_hours = prefs.get("daily_hours_default", 4.0)
    entries     = sched.generate_schedule(all_topics, daily_hours, today=date.today())

    # Merge SM-2 review sessions into the schedule
    due_reviews    = db.get_due_reviews(uid)
    review_entries = _reviews_to_schedule_entries(due_reviews, daily_hours)
    db.save_schedule(entries + review_entries, uid)

    total = len(entries) + len(review_entries)
    flash(f"Schedule generated — {len(entries)} study + {len(review_entries)} review sessions!", "success")
    return redirect(url_for("schedule"))


def _reviews_to_schedule_entries(due_reviews, daily_hours):
    """Convert SM-2 due-review rows into schedule entry dicts."""
    entries = []
    for r in due_reviews:
        if r["is_completed"]:
            continue
        entries.append({
            "topic_id":     r["topic_id"],
            "date":         r["next_review"],
            "hours":        min(round(r["estimated_hours"] * 0.4, 2), daily_hours),
            "entry_type":   "revision",
        })
    return entries


@app.route("/schedule/clear", methods=["POST"])
@login_required
def clear_schedule():
    db.save_schedule([], current_user.id)
    flash("Schedule cleared.", "info")
    return redirect(url_for("schedule"))


# ── Step 15: Drag-and-Drop — move a schedule entry ───────────────────────────

@app.route("/api/schedule/move", methods=["POST"])
@login_required
def api_schedule_move():
    data     = request.get_json(force=True)
    entry_id = data.get("entry_id")
    new_date = data.get("new_date")
    if not entry_id or not new_date:
        return jsonify({"error": "missing entry_id or new_date"}), 400
    try:
        # Validate date format
        date.fromisoformat(new_date)
    except ValueError:
        return jsonify({"error": "invalid date"}), 400
    db.move_schedule_entry(int(entry_id), new_date, current_user.id)
    return jsonify({"status": "moved", "entry_id": entry_id, "new_date": new_date})


# ── Reviews page ──────────────────────────────────────────────────────────────

@app.route("/reviews")
@login_required
def reviews():
    uid      = current_user.id
    due      = db.get_due_reviews(uid)
    all_revs = db.get_all_reviews(uid)
    return render_template("reviews.html",
                           due_reviews=due,
                           all_reviews=all_revs,
                           today=date.today().isoformat())


@app.route("/api/reviews/<int:topic_id>/rate", methods=["POST"])
@login_required
def rate_review(topic_id):
    """Receive a manual quality rating (0-5) and update SM-2 state."""
    uid     = current_user.id
    data    = request.get_json(force=True)
    quality = int(data.get("quality", 4))
    existing = db.get_review(topic_id, uid)
    if not existing:
        return jsonify({"error": "no review found"}), 404
    new_n, new_ease, new_interval, next_review = sr.sm2_next(
        existing["n"], existing["easiness"],
        existing["interval_days"], quality
    )
    db.upsert_review(topic_id, uid, new_n, new_ease,
                     new_interval, next_review, quality)
    return jsonify({
        "status":       "updated",
        "next_review":  next_review.isoformat(),
        "interval_days": new_interval,
        "easiness":     round(new_ease, 3),
    })


# ── Settings / Preferences ────────────────────────────────────────────────────

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    uid = current_user.id
    prefs = db.get_preferences(uid)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "preferences":
            db.update_preferences(
                uid,
                daily_hours_default   = float(request.form.get("daily_hours_default", 4.0)),
                theme                 = request.form.get("theme", "system"),
                notify_deadline_days  = int(request.form.get("notify_deadline_days", 3)),
                show_completed        = 1 if request.form.get("show_completed") else 0,
                default_difficulty    = int(request.form.get("default_difficulty", 3)),
            )
            flash("Preferences saved! ✅", "success")

        elif action == "account":
            username = request.form.get("username", "").strip()
            email    = request.form.get("email", "").strip().lower()
            # Check conflicts with OTHER users
            by_name  = db.get_user_by_username(username)
            by_email = db.get_user_by_email(email)
            if by_name  and by_name["id"]  != uid:
                flash("That username is already taken.", "error")
            elif by_email and by_email["id"] != uid:
                flash("That email is already in use.", "error")
            elif len(username) < 3:
                flash("Username must be at least 3 characters.", "error")
            else:
                err = db.update_account(uid, username, email)
                if err:
                    flash("Could not update account. Try again.", "error")
                else:
                    # Refresh the login session with new username
                    row = db.get_user_by_id(uid)
                    login_user(User(row), remember=True)
                    flash("Account updated! ✅", "success")

        elif action == "avatar":
            remove_avatar = request.form.get("remove_avatar")
            cropped_avatar = request.form.get("avatar_data", "")
            avatar_duration = request.form.get("avatar_media_duration", "")
            photo = request.files.get("avatar")
            if remove_avatar:
                db.update_avatar(uid, "")
                row = db.get_user_by_id(uid)
                login_user(User(row), remember=True)
                flash("Profile photo removed.", "info")
            elif cropped_avatar:
                try:
                    db.update_avatar(uid, _clean_profile_media_data_url(
                        cropped_avatar,
                        PROFILE_AVATAR_MEDIA_MAX_BYTES,
                        "Profile photo",
                        allow_animated=bool(current_user.is_verified),
                        duration_seconds=avatar_duration,
                    ))
                except ValueError as exc:
                    flash(str(exc), "error")
                else:
                    row = db.get_user_by_id(uid)
                    login_user(User(row), remember=True)
                    flash("Profile photo updated!", "success")
            elif not photo or not photo.filename:
                flash("Choose an image first.", "error")
            else:
                data = photo.read()
                content_type = (photo.mimetype or "").lower()
                encoded = base64.b64encode(data).decode("ascii")
                try:
                    db.update_avatar(uid, _clean_profile_media_data_url(
                        f"data:{content_type};base64,{encoded}",
                        PROFILE_AVATAR_MEDIA_MAX_BYTES,
                        "Profile photo",
                        allow_animated=bool(current_user.is_verified),
                        duration_seconds=avatar_duration,
                    ))
                except ValueError as exc:
                    flash(str(exc), "error")
                else:
                    row = db.get_user_by_id(uid)
                    login_user(User(row), remember=True)
                    flash("Profile photo updated!", "success")

        elif action == "banner":
            remove_banner = request.form.get("remove_banner")
            cropped_banner = request.form.get("banner_data", "")
            banner_duration = request.form.get("banner_media_duration", "")
            banner_file = request.files.get("banner")
            if remove_banner:
                db.update_banner(uid, "")
                row = db.get_user_by_id(uid)
                login_user(User(row), remember=True)
                flash("Profile banner removed.", "info")
            elif cropped_banner:
                try:
                    db.update_banner(uid, _clean_profile_media_data_url(
                        cropped_banner,
                        PROFILE_BANNER_MEDIA_MAX_BYTES,
                        "Profile banner",
                        allow_animated=bool(current_user.is_verified),
                        duration_seconds=banner_duration,
                    ))
                except ValueError as exc:
                    flash(str(exc), "error")
                else:
                    row = db.get_user_by_id(uid)
                    login_user(User(row), remember=True)
                    flash("Profile banner updated!", "success")
            elif not banner_file or not banner_file.filename:
                flash("Choose a banner image first.", "error")
            else:
                data = banner_file.read()
                content_type = (banner_file.mimetype or "").lower()
                encoded = base64.b64encode(data).decode("ascii")
                try:
                    db.update_banner(uid, _clean_profile_media_data_url(
                        f"data:{content_type};base64,{encoded}",
                        PROFILE_BANNER_MEDIA_MAX_BYTES,
                        "Profile banner",
                        allow_animated=bool(current_user.is_verified),
                        duration_seconds=banner_duration,
                    ))
                except ValueError as exc:
                    flash(str(exc), "error")
                else:
                    row = db.get_user_by_id(uid)
                    login_user(User(row), remember=True)
                    flash("Profile banner updated!", "success")

        elif action == "decoration":
            decoration = request.form.get("profile_decoration", "")
            if decoration not in {"", *PROFILE_DECORATION_ASSETS.keys()}:
                decoration = ""
            if decoration and not _can_use_profile_decoration(current_user, decoration):
                flash("Redeem that avatar decoration before using it.", "error")
            else:
                db.update_profile_decoration(uid, decoration)
                row = db.get_user_by_id(uid)
                login_user(User(row), remember=True)
                flash("Profile decoration updated!", "success")

        elif action == "password":
            from werkzeug.security import check_password_hash, generate_password_hash
            current_pw  = request.form.get("current_password", "")
            new_pw      = request.form.get("new_password", "")
            confirm_pw  = request.form.get("confirm_password", "")
            user_row    = db.get_user_by_id(uid)
            if not check_password_hash(user_row["password_hash"], current_pw):
                flash("Current password is incorrect.", "error")
            elif len(new_pw) < 6:
                flash("New password must be at least 6 characters.", "error")
            elif new_pw != confirm_pw:
                flash("New passwords do not match.", "error")
            else:
                db.update_password(uid, generate_password_hash(new_pw))
                flash("Password changed successfully! 🔒", "success")

        return redirect(url_for("settings"))

    user_row = db.get_user_by_id(uid)
    if user_row.get("profile_decoration") and not _can_use_profile_decoration(current_user, user_row["profile_decoration"]):
        db.update_profile_decoration(uid, "")
        user_row = db.get_user_by_id(uid)
        login_user(User(user_row), remember=True)
    return render_template("settings.html", prefs=prefs, user=user_row)


# ── Analytics ─────────────────────────────────────────────────────────────────

@app.route("/analytics")
@login_required
def analytics():
    uid  = current_user.id
    data = db.get_analytics_data(uid)
    streak = db.get_streak(uid)
    return render_template("analytics.html",
                           data=data, streak=streak,
                           data_json=json_lib.dumps(data))


# ── API endpoints ─────────────────────────────────────────────────────────────

@app.route("/api/stats")
@login_required
def api_stats():
    return jsonify(db.get_dashboard_stats(current_user.id))


@app.route("/api/profile-media/sign", methods=["POST"])
@login_required
def sign_profile_media():
    if not CLOUDINARY_UPLOAD_ENABLED:
        return jsonify({"error": "Cloudinary is not configured."}), 503

    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "avatar")
    resource_type = data.get("resource_type", "auto")
    if mode not in {"avatar", "banner"}:
        return jsonify({"error": "Invalid upload target."}), 400
    if resource_type not in {"auto", "image", "video"}:
        resource_type = "auto"
    if resource_type == "video" and not current_user.is_verified:
        return jsonify({"error": "Animated profile media is verified-only."}), 403

    timestamp = int(time.time())
    params = {
        "folder": CLOUDINARY_PROFILE_FOLDER,
        "timestamp": timestamp,
    }
    cloud_name = CLOUDINARY_CLOUD_NAME
    return jsonify({
        "apiKey": CLOUDINARY_API_KEY,
        "cloudName": cloud_name,
        "folder": CLOUDINARY_PROFILE_FOLDER,
        "timestamp": timestamp,
        "signature": _cloudinary_signature(params),
        "uploadUrl": f"https://api.cloudinary.com/v1_1/{cloud_name}/auto/upload",
    })


# ── Ollama AI endpoints ───────────────────────────────────────────────────────

# ── Groq API Configuration ────────────────────────────────────────────────────

from groq import Groq

GROQ_API_KEY      = os.environ.get("GROQ_API_KEY", "")
GROQ_FAST_MODEL   = os.environ.get("GROQ_FAST_MODEL", "llama-3.1-8b-instant")
GROQ_HEAVY_MODEL  = os.environ.get("GROQ_HEAVY_MODEL", "llama-3.3-70b-versatile")
STUDYFLOW_APP_CONTEXT = (
    "StudyFlow was created by Ved Patel and Deepshikha Rani."
)

_groq_client: Groq | None = None

def _get_groq_client() -> Groq:
    """Return a cached Groq client, raising RuntimeError if key is missing."""
    global _groq_client
    if _groq_client is None:
        key = GROQ_API_KEY
        if not key:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")
        _groq_client = Groq(api_key=key)
    return _groq_client


def call_groq(prompt: str, system: str = "", model: str | None = None,
              max_tokens: int = 1024) -> str:
    """Single-turn generation via Groq."""
    client = _get_groq_client()
    model = model or GROQ_FAST_MODEL
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"Groq error: {e}")


# Keep legacy names so no other call-site in app.py needs changing
def call_ollama(prompt: str, system: str = "", model: str | None = None,
                max_tokens: int = 1024) -> str:
    return call_groq(prompt, system, model, max_tokens)


def call_groq_chat(messages: list, system: str = "",
                   model: str | None = None) -> str:
    """Multi-turn chat via Groq."""
    client = _get_groq_client()
    model = model or GROQ_FAST_MODEL
    full_messages = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=full_messages,
            max_tokens=1024,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"Groq chat error: {e}")


# Keep legacy name
def call_ollama_chat(messages: list, system: str = "") -> str:
    return call_groq_chat(messages, system)


# ── Step 19: AI Chat with Memory (Groq streaming) ────────────────────────────

@app.route("/api/ai/chat", methods=["POST"])
@login_required
def ai_chat():
    data     = request.get_json(force=True)
    user_msg = (data.get("message") or "").strip()
    history  = data.get("history") or []

    if not user_msg:
        return jsonify({"error": "empty message"}), 400

    system = (
        "You are StudyFlow AI, a friendly and concise study assistant embedded "
        "in a study planner. Answer in 3-6 sentences. Use markdown bullets when listing. "
        f"Important app context: {STUDYFLOW_APP_CONTEXT} "
        f"The student's name is {current_user.username}."
    )

    messages = history[-10:] + [{"role": "user", "content": user_msg}]

    try:
        reply = call_groq_chat(messages, system)
        return jsonify({"reply": reply})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503


# ── Step 16: AI Difficulty Auto-Rating ───────────────────────────────────────

@app.route("/api/ai/suggest-difficulty", methods=["POST"])
@login_required
def ai_suggest_difficulty():
    data       = request.get_json(force=True)
    topic_name = (data.get("topic_name") or "").strip()
    subject    = (data.get("subject_name") or "").strip()
    if not topic_name:
        return jsonify({"error": "topic_name required"}), 400

    prompt = (
        f"Rate the academic difficulty of studying '{topic_name}'"
        + (f" in {subject}" if subject else "")
        + " on a scale of 1 to 5 where:\n"
        "1 = Easy (basic recall, definitions)\n"
        "2 = Moderate (some application)\n"
        "3 = Medium (concepts + practice)\n"
        "4 = Hard (complex problem solving)\n"
        "5 = Expert (proofs, deep theory)\n\n"
        "Reply with ONLY a JSON object like: "
        '{\"difficulty\": 3, \"reason\": \"one short sentence\"}'
    )
    system = (
        "You are an academic difficulty rater. "
        "Reply ONLY with valid JSON — no markdown, no extra text."
    )
    try:
        raw = call_ollama(prompt, system)
        # Strip any accidental markdown fences
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        parsed = json_lib.loads(raw)
        diff   = max(1, min(5, int(parsed.get("difficulty", 3))))
        reason = str(parsed.get("reason", ""))[:120]
        return jsonify({"difficulty": diff, "reason": reason})
    except Exception as e:
        return jsonify({"error": str(e)}), 503


# ── Phase 7: AI Auto-Fill Topic Form ─────────────────────────────────────────

@app.route("/api/ai/autofill-topic", methods=["POST"])
@login_required
def ai_autofill_topic():
    data       = request.get_json(force=True)
    topic_name = (data.get("topic_name") or "").strip()
    subject    = (data.get("subject_name") or "").strip()
    if not topic_name:
        return jsonify({"error": "topic_name required"}), 400

    today_str  = date.today().isoformat()
    in_30_days = (date.today() + timedelta(days=30)).isoformat()

    prompt = (
        f"You are helping a BTech student plan their study schedule.\n"
        f"Topic: '{topic_name}'" + (f"  Subject: {subject}" if subject else "") + "\n"
        f"Today: {today_str}\n\n"
        "Return three values based on typical university curriculum:\n"
        "  difficulty: integer 1-5 (1=Easy, 3=Medium, 5=Expert)\n"
        "  estimated_hours: realistic total hours to study this topic (0.5 to 80)\n"
        "  suggested_deadline: a date at least 7 days from today in YYYY-MM-DD format\n\n"
        "Reply ONLY with this exact JSON structure, no markdown:\n"
        '{"difficulty": 3, "estimated_hours": 8, '
        '"suggested_deadline": "' + in_30_days + '", '
        '"reason": "one short sentence explaining your choices"}'
    )
    system = "Academic study planner. Reply ONLY with valid JSON, no markdown fences or explanation."

    try:
        raw    = call_ollama(prompt, system)
        raw    = raw.strip()
        # Robust extraction: find first { ... }
        start  = raw.find("{")
        end    = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON in response")
        parsed = json_lib.loads(raw[start:end])

        diff     = max(1, min(5, int(float(parsed.get("difficulty", 3)))))
        hours    = max(0.5, min(80.0, float(parsed.get("estimated_hours", 6))))
        deadline = str(parsed.get("suggested_deadline", in_30_days)).strip()
        if deadline <= today_str:
            deadline = (date.today() + timedelta(days=14)).isoformat()
        reason   = str(parsed.get("reason", ""))[:180]

        return jsonify({
            "difficulty":         diff,
            "estimated_hours":    round(hours, 1),
            "suggested_deadline": deadline,
            "reason":             reason,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ai/status")
@login_required
def ai_status():
    """Returns Groq API status and active model name for the sidebar indicator."""
    key = GROQ_API_KEY
    if not key:
        return jsonify({"online": False, "model": None,
                        "error": "GROQ_API_KEY not set"})
    try:
        client = _get_groq_client()
        # Lightweight ping: list models
        models = client.models.list()
        model_ids = [m.id for m in models.data] if models.data else []
        active = GROQ_FAST_MODEL if GROQ_FAST_MODEL in model_ids else (
            model_ids[0] if model_ids else GROQ_FAST_MODEL)
        return jsonify({"online": True, "model": active,
                        "fast_model": GROQ_FAST_MODEL,
                        "heavy_model": GROQ_HEAVY_MODEL})
    except Exception as e:
        return jsonify({"online": False, "model": None, "error": str(e)})


# ── Phase 7: Practice Session Page ───────────────────────────────────────────

@app.route("/practice")
@login_required
def practice():
    subjects = db.get_all_subjects(current_user.id)
    return render_template("practice.html", subjects=subjects)


@app.route("/api/ai/practice-paper", methods=["POST"])
@login_required
def ai_practice_paper():
    data       = request.get_json(force=True)
    topic_name = (data.get("topic") or "").strip()
    subject    = (data.get("subject") or "").strip()
    difficulty = (data.get("difficulty") or "Medium").strip()

    if not topic_name:
        return jsonify({"error": "topic required"}), 400

    ctx = f"'{topic_name}'" + (f" ({subject})" if subject else "")

    def extract_json_array(text):
        """Robustly extract a JSON array from messy LLM output."""
        import re
        text = text.strip()

        # 1) Strip markdown code fences (```json ... ``` or ``` ... ```)
        text = re.sub(r"```(?:json)?\s*", "", text).strip()

        # 2) Find the outermost [ ... ] with balanced bracket matching
        start = text.find("[")
        if start == -1:
            raise ValueError(f"No JSON array found. Got: {text[:200]}")

        depth = 0
        in_str = False
        escape = False
        end = -1
        for i, ch in enumerate(text[start:], start):
            if escape:
                escape = False
                continue
            if ch == "\\" and in_str:
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = i
                    break

        if end == -1:
            raise ValueError(f"Unbalanced JSON array. Got: {text[:200]}")

        candidate = text[start:end + 1]
        try:
            return json_lib.loads(candidate)
        except json_lib.JSONDecodeError as exc:
            raise ValueError(f"JSON parse error: {exc}. Snippet: {candidate[:200]}")

    def build_prompt(qtype, count, num_start):
        if qtype == "MCQ":
            fmt = (
                '{"num": ' + str(num_start) + ', "type": "MCQ", '
                '"question": "Question text here?", '
                '"options": {"A": "First option", "B": "Second option", '
                '"C": "Third option", "D": "Fourth option"}, "answer": "A"}'
            )
            instruction = (
                f"Generate exactly {count} multiple-choice questions about {ctx}. "
                "Each must have a 'question', 'options' (keys A B C D), and 'answer' (one letter). "
                f"Number them {num_start} to {num_start + count - 1}."
            )
        elif qtype == "TF":
            fmt = (
                '{"num": ' + str(num_start) + ', "type": "TF", '
                '"question": "Statement here.", "options": null, "answer": "True"}'
            )
            instruction = (
                f"Generate exactly {count} True/False questions about {ctx}. "
                "Each must have a 'question' and 'answer' (exactly 'True' or 'False'). "
                f"Number them {num_start} to {num_start + count - 1}."
            )
        else:
            fmt = (
                '{"num": ' + str(num_start) + ', "type": "SA", '
                '"question": "Question here?", "options": null, '
                '"answer": "Concise model answer in 1-2 sentences."}'
            )
            instruction = (
                f"Generate exactly {count} short-answer questions about {ctx}. "
                "Each must have a 'question' and 'answer' (1-2 sentence model answer). "
                f"Number them {num_start} to {num_start + count - 1}."
            )

        return (
            f"Topic: {ctx}. Difficulty: {difficulty}.\n\n"
            f"{instruction}\n\n"
            f"Respond with ONLY a raw JSON array. No markdown. No code fences. "
            f"No explanation. Start your response with [ and end with ].\n\n"
            f"Example of one item: {fmt}"
        )

    system = (
        "You are a JSON-only exam question generator. "
        "You MUST respond with a raw JSON array starting with [ and ending with ]. "
        "Never use markdown. Never add explanation. Only output the JSON array."
    )

    # Helper: call with retries
    def call_with_retry(prompt, retries=2):
        last_err = None
        for attempt in range(retries + 1):
            try:
                raw = call_ollama(prompt, system,
                                  model=GROQ_HEAVY_MODEL, max_tokens=4096)
                return extract_json_array(raw)
            except Exception as e:
                last_err = e
        raise last_err

    try:
        all_questions = []

        # Split 15 MCQs into 3 batches of 5 to stay well within token limits
        mcqs = []
        for batch_start in [1, 6, 11]:
            mcqs.extend(call_with_retry(build_prompt("MCQ", 5, batch_start)))

        # 8 True/False
        tfs = call_with_retry(build_prompt("TF", 8, 16))

        # 7 Short Answer
        sas = call_with_retry(build_prompt("SA", 7, 24))

        # Merge and normalise
        num = 1
        for batch, expected_type in [(mcqs, "MCQ"), (tfs, "TF"), (sas, "SA")]:
            for q in batch:
                if not isinstance(q, dict):
                    continue
                qtype = str(q.get("type", expected_type)).upper()
                if qtype not in ("MCQ", "TF", "SA"):
                    qtype = expected_type
                question_text = str(q.get("question", "")).strip()
                if not question_text:
                    continue
                item = {
                    "num":      num,
                    "type":     qtype,
                    "question": question_text,
                    "options":  q.get("options") if qtype == "MCQ" else None,
                    "answer":   str(q.get("answer", "")).strip(),
                }
                # Ensure MCQ has valid options dict
                if qtype == "MCQ" and not isinstance(item["options"], dict):
                    item["options"] = {"A": "Option A", "B": "Option B",
                                       "C": "Option C", "D": "Option D"}
                all_questions.append(item)
                num += 1

        if not all_questions:
            return jsonify({"error": "AI returned no questions — try again."}), 503

        return jsonify({
            "questions": all_questions,
            "topic":     topic_name,
            "subject":   subject,
            "difficulty": difficulty,
            "total":     len(all_questions),
        })

    except Exception as e:
        return jsonify({"error": f"Generation failed: {str(e)[:200]}"}), 503

@app.route("/api/ai/readiness/<int:subject_id>")
@login_required
def ai_readiness(subject_id):
    uid      = current_user.id
    topics   = db.get_topics_by_subject(subject_id, uid)
    if not topics:
        return jsonify({"score": 0, "label": "No topics", "color": "#94a3b8"})

    today_str = date.today().isoformat()
    total     = len(topics)
    completed = sum(1 for t in topics if t["is_completed"])
    pending   = [t for t in topics if not t["is_completed"]]
    avg_diff  = (sum(t["difficulty"] for t in pending) / len(pending)) if pending else 0

    # Days to nearest deadline
    upcoming = [t for t in pending if t["deadline"] >= today_str]
    days_left = min(
        (date.fromisoformat(t["deadline"]) - date.today()).days
        for t in upcoming
    ) if upcoming else 999

    prompt = (
        f"Exam readiness assessment:\n"
        f"- Topics completed: {completed}/{total} ({int(completed/total*100)}%)\n"
        f"- Pending topics avg difficulty: {avg_diff:.1f}/5\n"
        f"- Days until nearest deadline: {days_left}\n"
        f"- Pending topics: {', '.join(t['name'] for t in pending[:5])}\n\n"
        "Give an exam readiness score out of 100 and one short reason (under 15 words).\n"
        "Reply ONLY with JSON: "
        '{\"score\": 72, \"label\": \"On track\", \"tip\": \"short tip here\"}'
    )
    system = "Academic readiness rater. Reply ONLY with valid JSON, no markdown."

    try:
        raw    = call_ollama(prompt, system)
        raw    = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        parsed = json_lib.loads(raw)
        score  = max(0, min(100, int(parsed.get("score", 50))))
        label  = str(parsed.get("label", ""))[:30]
        tip    = str(parsed.get("tip",   ""))[:100]
        # Colour by score
        color  = ("#10b981" if score >= 75 else
                  "#f59e0b" if score >= 45 else "#f43f5e")
        return jsonify({"score": score, "label": label, "tip": tip, "color": color})
    except Exception as e:
        return jsonify({"error": str(e)}), 503


# ── Step 18: AI Quiz Questions ────────────────────────────────────────────────

@app.route("/api/ai/quiz/<int:topic_id>")
@login_required
def ai_quiz(topic_id):
    uid    = current_user.id
    topics = db.get_all_topics(uid)
    topic  = next((t for t in topics if t["id"] == topic_id), None)
    if not topic:
        return jsonify({"error": "topic not found"}), 404

    prompt = (
        f"Create exactly 5 multiple-choice quiz questions about '{topic['name']}' "
        f"(difficulty {topic['difficulty']}/5, subject: {topic['subject_name']}).\n\n"
        "Each question must have 4 options (A–D) and one correct answer.\n"
        "Reply ONLY with a JSON array — no markdown, no extra text:\n"
        '[\n'
        '  {\n'
        '    "q": "Question text?",\n'
        '    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},\n'
        '    "answer": "B"\n'
        '  }\n'
        ']'
    )
    system = "Quiz generator. Reply ONLY with a valid JSON array, no markdown fences."

    try:
        import re as _re
        raw  = call_ollama(prompt, system, model=GROQ_HEAVY_MODEL, max_tokens=2048)
        raw  = _re.sub(r"```(?:json)?\s*", "", raw).strip()

        # Balanced-bracket extraction
        start = raw.find("[")
        if start == -1:
            raise ValueError("No JSON array found in response")
        depth, in_str, escape, end = 0, False, False, -1
        for i, ch in enumerate(raw[start:], start):
            if escape: escape = False; continue
            if ch == "\\" and in_str: escape = True; continue
            if ch == '"': in_str = not in_str; continue
            if in_str: continue
            if ch == "[": depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0: end = i; break
        if end == -1:
            raise ValueError("Unbalanced JSON array in response")
        questions = json_lib.loads(raw[start:end + 1])
        # Validate structure
        validated = []
        for item in questions[:5]:
            if "q" in item and "options" in item and "answer" in item:
                validated.append({
                    "q":       str(item["q"]),
                    "options": {k: str(v) for k, v in item["options"].items()
                                if k in "ABCD"},
                    "answer":  str(item["answer"]).upper()[:1],
                })
        return jsonify({"questions": validated, "topic": topic["name"],
                        "topic_id": topic_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ai/topic-tips/<int:topic_id>")
@login_required
def ai_topic_tips(topic_id):
    topic = next((t for t in db.get_all_topics(current_user.id) if t["id"] == topic_id), None)
    if not topic:
        return jsonify({"error": "topic not found"}), 404
    prompt = (f"I need to study '{topic['name']}' (difficulty {topic['difficulty']}/5, "
              f"~{topic['estimated_hours']}h). Give 5 specific, actionable study tips.")
    try:
        return jsonify({"tips": call_ollama(prompt,
            "You are a study coach. Numbered list, under 200 words."), "topic": topic["name"]})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ai/schedule-insights")
@login_required
def ai_schedule_insights():
    from collections import defaultdict
    entries = db.get_schedule(current_user.id)
    if not entries:
        return jsonify({"error": "no schedule yet"}), 400
    today_str = date.today().isoformat()
    daily = defaultdict(float)
    topic_hours = defaultdict(float)
    for e in entries:
        daily[e["date"]] += e["hours"]
        topic_hours[e["topic_name"]] += e["hours"]
    summary = (f"{len(entries)} sessions across {len(daily)} days. "
               f"Upcoming: " + ", ".join(f"{d}:{h:.1f}h" for d,h in sorted(daily.items()) if d>=today_str)[:200])
    prompt = (f"Schedule: {summary}\n\nGive 4 insights: workload balance, burnout risk, "
              "revision coverage, one improvement suggestion.")
    try:
        return jsonify({"insights": call_ollama(prompt,
            "Study schedule analyst. 4 numbered points, under 180 words.")})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ai/dashboard-advice")
@login_required
def ai_dashboard_advice():
    stats = db.get_dashboard_stats(current_user.id)
    deadlines = ", ".join(
        f"{d['topic_name']} ({d['deadline']}, diff {d['difficulty']}/5)"
        for d in stats.get("upcoming_deadlines", [])[:5]
    ) or "none"
    prompt = (f"Stats: {stats['total_subjects']} subjects, {stats['total_topics']} topics, "
              f"{stats['pending_topics']} pending, {stats['completed_topics']} done. "
              f"Deadlines: {deadlines}. Give today's plan in 3 bullet points.")
    try:
        return jsonify({"advice": call_ollama(prompt,
            "Daily study coach. 3 bullet points, under 120 words. Warm and motivating.")})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503


if __name__ == "__main__":
    app.run(debug=True, port=5000)
