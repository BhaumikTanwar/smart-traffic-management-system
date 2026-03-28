"""
app.py
------
- Flask-SocketIO: server pushes traffic updates every 3s
- Iterative spiderweb propagation (3 rounds)
- SQLite history endpoints
- open_video / release_video lifecycle
"""

import os
import random
import threading
import time

from flask import Flask, render_template, request, redirect, url_for, session
from flask import jsonify, Response, send_file
from flask_socketio import SocketIO, emit

from services.traffic_service import get_traffic_status
from services.video_service   import detect_vehicles_from_video, generate_video_stream
from services.video_service   import open_video, release_video
from services.db_service      import init_db, get_recent_traffic, get_daily_summary, log_spiderweb, get_spiderweb_history

# ── App setup ──────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "../frontend/templates"),
    static_folder=os.path.join(BASE_DIR, "../frontend/static")
)
app.secret_key = "THIS_IS_A_FIXED_SECRET_KEY_12345"

# async_mode='threading' is required for background threads with Flask-SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ── Init DB once ───────────────────────────────────────
init_db()

# ── Users ──────────────────────────────────────────────
USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "user":  {"password": "user123",  "role": "user"},
}

# ── Mode state ─────────────────────────────────────────
CURRENT_MODE = "simulation"
VIDEO_PATH   = os.path.join(BASE_DIR, "uploaded_video.mp4")

# ─────────────────────────────────────────────────────
# BACKGROUND THREAD: push traffic updates via SocketIO
# ─────────────────────────────────────────────────────
_bg_thread      = None
_bg_thread_lock = threading.Lock()

def background_traffic_push():
    """Runs forever; emits 'traffic_update' to all connected clients every 3s."""
    while True:
        try:
            data = get_traffic_status(CURRENT_MODE)
            socketio.emit("traffic_update", data)
        except Exception as e:
            print("⚠️  Push error:", e)
        socketio.sleep(3)

@socketio.on("connect")
def on_connect():
    global _bg_thread
    with _bg_thread_lock:
        if _bg_thread is None or not _bg_thread.is_alive():
            _bg_thread = socketio.start_background_task(background_traffic_push)
    # send one immediate reading
    emit("traffic_update", get_traffic_status(CURRENT_MODE))


# ─────────────────────────────────────────────────────
# SPIDERWEB  — iterative propagation (3 rounds)
# ─────────────────────────────────────────────────────
@app.route("/api/spiderweb-data", methods=["POST"])
def spiderweb_data():
    data  = request.get_json()
    nodes = data.get("nodes", {})
    edges = data.get("edges", {})

    # Seed: each node gets a random base load
    congestion = {node: random.randint(5, 30) for node in nodes}

    # Iterative propagation — 3 rounds
    ROUNDS      = 3
    DECAY       = 0.85   # congestion decays slightly each round
    SPREAD      = 0.35   # fraction passed to each neighbour

    for _ in range(ROUNDS):
        new_cong = {}
        for node in nodes:
            neighbours = edges.get(node, [])
            # own value decays
            own = congestion[node] * DECAY
            # absorb influence from neighbours
            neighbour_influence = sum(
                congestion.get(nb, 0) * SPREAD
                for nb in neighbours
            )
            new_cong[node] = int(own + neighbour_influence)
        congestion = new_cong

    # Clamp to [5, 90]
    congestion = {n: max(5, min(90, v)) for n, v in congestion.items()}

    # Log snapshot to DB
    try:
        log_spiderweb(congestion)
    except Exception as e:
        print("⚠️  Spiderweb DB log error:", e)

    return jsonify(congestion)


# ─────────────────────────────────────────────────────
# HISTORY API  (for dashboard charts)
# ─────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────
# VIDEO ROUTES
# ─────────────────────────────────────────────────────
@app.route("/get-video")
def get_video():
    if not os.path.exists(VIDEO_PATH):
        return "No video", 404
    return send_file(VIDEO_PATH)

@app.route("/video_feed")
def video_feed():
    return Response(
        generate_video_stream(VIDEO_PATH),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@app.route("/upload-video", methods=["POST"])
def upload_video():
    video = request.files["video"]
    video.save(VIDEO_PATH)
    print("✅ Video saved at:", VIDEO_PATH)
    open_video(VIDEO_PATH)
    return jsonify({"status": "uploaded"})


# ─────────────────────────────────────────────────────
# PAGES
# ─────────────────────────────────────────────────────
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
            return redirect(url_for("admin" if session["role"] == "admin" else "user"))
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
    session.clear()
    return redirect(url_for("login"))


# ─────────────────────────────────────────────────────
# MODE SWITCHING
# ─────────────────────────────────────────────────────
@app.route("/set-mode/<mode>")
def set_mode(mode):
    global CURRENT_MODE
    if mode not in ["simulation", "video"]:
        return jsonify({"error": "Invalid mode"}), 400

    CURRENT_MODE = mode

    if mode == "simulation":
        release_video()
        if os.path.exists(VIDEO_PATH):
            try:
                os.remove(VIDEO_PATH)
                print("✅ Uploaded video deleted")
            except Exception as e:
                print("❌ Error deleting video:", e)

    return jsonify({"current_mode": CURRENT_MODE})


# ─────────────────────────────────────────────────────
# LEGACY polling endpoint (kept for compatibility)
# ─────────────────────────────────────────────────────
@app.route("/api/traffic-status")
def traffic_status():
    return jsonify(get_traffic_status(CURRENT_MODE))


# ─────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────
if __name__ == "__main__":
    socketio.run(app, debug=True)
