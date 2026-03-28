"""
app.py
------
- Secrets loaded from .env (python-dotenv)
- Thread-safe CURRENT_MODE with a Lock
- Structured logging (replaces print statements)
- Congestion alert emitted via SocketIO when level is High
- All previous routes preserved
"""

import os
import logging
import random
import threading
import time

from flask import Flask, render_template, request, redirect, url_for, session
from flask import jsonify, Response, send_file
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv

from services.traffic_service import get_traffic_status
from services.video_service   import detect_vehicles_from_video, generate_video_stream
from services.video_service   import open_video, release_video
from services.db_service      import init_db, get_recent_traffic, get_daily_summary, log_spiderweb, get_spiderweb_history

# ── Logging ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("app")

# ── Load .env ──────────────────────────────────────────
load_dotenv()

# ── App setup ──────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "../frontend/templates"),
    static_folder=os.path.join(BASE_DIR, "../frontend/static"),
)
app.secret_key = os.getenv("SECRET_KEY", "change-me-in-production")

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

init_db()

# ── Users (load from env; fall back to defaults for local dev only) ────
USERS = {
    os.getenv("ADMIN_USER", "admin"): {
        "password": os.getenv("ADMIN_PASS", "admin123"),
        "role": "admin",
    },
    os.getenv("USER_USER", "user"): {
        "password": os.getenv("USER_PASS", "user123"),
        "role": "user",
    },
}

# ── Thread-safe mode state ─────────────────────────────
_mode_lock   = threading.Lock()
_current_mode = "simulation"
VIDEO_PATH   = os.path.join(BASE_DIR, "uploaded_video.mp4")


def get_mode() -> str:
    with _mode_lock:
        return _current_mode


def set_mode_internal(mode: str):
    global _current_mode
    with _mode_lock:
        _current_mode = mode


# ── Background push thread ─────────────────────────────
_bg_thread      = None
_bg_thread_lock = threading.Lock()


def background_traffic_push():
    while True:
        try:
            data = get_traffic_status(get_mode())
            socketio.emit("traffic_update", data)

            # Emit a separate alert if any road is High
            for road in data.get("roads", []):
                if road.get("congestion_level") == "High":
                    socketio.emit("congestion_alert", {
                        "level":   "High",
                        "message": "High congestion detected — expect delays.",
                    })
                    break
        except Exception as e:
            log.warning("Push error: %s", e)
        socketio.sleep(3)


@socketio.on("connect")
def on_connect():
    global _bg_thread
    with _bg_thread_lock:
        if _bg_thread is None or not _bg_thread.is_alive():
            _bg_thread = socketio.start_background_task(background_traffic_push)
    emit("traffic_update", get_traffic_status(get_mode()))


# ── Spiderweb ──────────────────────────────────────────
@app.route("/api/spiderweb-data", methods=["POST"])
def spiderweb_data():
    data  = request.get_json()
    nodes = data.get("nodes", {})
    edges = data.get("edges", {})

    congestion = {node: random.randint(5, 30) for node in nodes}

    ROUNDS = 3
    DECAY  = 0.85
    SPREAD = 0.35

    for _ in range(ROUNDS):
        new_cong = {}
        for node in nodes:
            neighbours        = edges.get(node, [])
            own               = congestion[node] * DECAY
            neighbour_influence = sum(congestion.get(nb, 0) * SPREAD for nb in neighbours)
            new_cong[node]    = int(own + neighbour_influence)
        congestion = new_cong

    congestion = {n: max(5, min(90, v)) for n, v in congestion.items()}

    try:
        log_spiderweb(congestion)
    except Exception as e:
        log.warning("Spiderweb DB log error: %s", e)

    return jsonify(congestion)


# ── History API ────────────────────────────────────────
@app.route("/api/history")
def history():
    limit = int(request.args.get("limit", 30))
    return jsonify(get_recent_traffic(limit))


@app.route("/api/daily-summary")
def daily_summary():
    return jsonify(get_daily_summary())


@app.route("/api/spiderweb-history/<node>")
def spiderweb_history(node):
    return jsonify(get_spiderweb_history(node, limit=20))


# ── Data export (new) ─────────────────────────────────
@app.route("/api/export/traffic")
def export_traffic():
    """Download all traffic_log rows as CSV."""
    import io, csv
    from services.db_service import get_conn
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT timestamp,mode,vehicle_count,congestion,future_cong,green_time FROM traffic_log ORDER BY id"
        ).fetchall()
    buf = io.StringIO()
    w   = csv.writer(buf)
    w.writerow(["timestamp", "mode", "vehicle_count", "congestion", "future_cong", "green_time"])
    w.writerows(rows)
    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=traffic_export.csv"},
    )


# ── Video routes ───────────────────────────────────────
@app.route("/get-video")
def get_video():
    if not os.path.exists(VIDEO_PATH):
        return "No video", 404
    return send_file(VIDEO_PATH)


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_video_stream(VIDEO_PATH),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/upload-video", methods=["POST"])
def upload_video():
    video = request.files["video"]
    video.save(VIDEO_PATH)
    log.info("Video saved: %s", VIDEO_PATH)
    open_video(VIDEO_PATH)
    return jsonify({"status": "uploaded"})


# ── Pages ──────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/spiderweb")
def spiderweb():
    return render_template("spiderweb.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username in USERS and USERS[username]["password"] == password:
            session.clear()
            session["username"] = username
            session["role"]     = USERS[username]["role"]
            log.info("Login: %s (%s)", username, session["role"])
            return redirect(url_for("admin" if session["role"] == "admin" else "user"))
        log.warning("Failed login attempt for user: %s", username)
        return "INVALID USERNAME OR PASSWORD"
    return render_template("login.html")


@app.route("/admin")
def admin():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    return render_template("admin.html", username=session["username"])


@app.route("/user")
def user():
    if session.get("role") != "user":
        return redirect(url_for("login"))
    return render_template("user.html", username=session["username"])


@app.route("/logout")
def logout():
    log.info("Logout: %s", session.get("username"))
    session.clear()
    return redirect(url_for("login"))


# ── Mode switching ─────────────────────────────────────
@app.route("/set-mode/<mode>")
def set_mode(mode):
    if mode not in ["simulation", "video"]:
        return jsonify({"error": "Invalid mode"}), 400

    set_mode_internal(mode)

    if mode == "simulation":
        release_video()
        if os.path.exists(VIDEO_PATH):
            try:
                os.remove(VIDEO_PATH)
                log.info("Uploaded video deleted")
            except Exception as e:
                log.error("Error deleting video: %s", e)

    return jsonify({"current_mode": get_mode()})


# ── Legacy polling ─────────────────────────────────────
@app.route("/api/traffic-status")
def traffic_status():
    return jsonify(get_traffic_status(get_mode()))


# ── Run ────────────────────────────────────────────────
if __name__ == "__main__":
    socketio.run(app, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
