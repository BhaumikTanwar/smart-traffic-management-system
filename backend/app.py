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
from services.osm_service     import fetch_osm_network

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


# ── OSM network ────────────────────────────────────────
@app.route("/api/osm-network")
def osm_network():
    try:
        net = fetch_osm_network()
        return jsonify(net)
    except Exception as e:
        log.error("OSM network error: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/osm-refresh")
def osm_refresh():
    try:
        net = fetch_osm_network(force=True)
        return jsonify({"status": "refreshed", "nodes": len(net["nodes"])})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Spiderweb state ────────────────────────────────────
_spider_state = {}
_spider_lock  = threading.Lock()
TOTAL_VEHICLE_POOL = 500   # conservation anchor


@app.route("/api/spiderweb-data", methods=["POST"])
def spiderweb_data():
    data       = request.get_json()
    nodes      = data.get("nodes", {})
    edges      = data.get("edges", {})
    roles      = data.get("roles", {})
    generators = [n for n in nodes if roles.get(n) == "generator"]
    sinks      = [n for n in nodes if roles.get(n) == "sink"]

    FLOW_RATE     = 0.28
    SINK_DRAIN    = 0.40
    GEN_RATE      = 0.15
    GEN_BOOST_MIN = 30
    GEN_BOOST_MAX = 60
    NOISE         = 1.2

    with _spider_lock:
        # Seed new nodes
        for node in nodes:
            if node not in _spider_state:
                role = roles.get(node, "normal")
                if role == "generator":
                    _spider_state[node] = random.uniform(40, 65)
                elif role == "sink":
                    _spider_state[node] = random.uniform(5, 15)
                else:
                    neighbours = edges.get(node, [])
                    if neighbours:
                        avg_nb = sum(_spider_state.get(nb, 20) for nb in neighbours) / len(neighbours)
                        _spider_state[node] = avg_nb * 0.25
                    else:
                        _spider_state[node] = random.uniform(10, 30)

        # Remove deleted nodes
        for gone in [n for n in list(_spider_state) if n not in nodes]:
            del _spider_state[gone]

        # Generator injection
        for gen in generators:
            if random.random() < GEN_RATE:
                boost = random.uniform(GEN_BOOST_MIN, GEN_BOOST_MAX)
                _spider_state[gen] = min(90, _spider_state[gen] + boost)
                log.info("Generator event at %s (+%.0f)", gen, boost)

        # Vehicle-conserving flow
        delta = {node: 0.0 for node in nodes}

        for node in nodes:
            neighbours = edges.get(node, [])
            if not neighbours:
                continue

            own_load = _spider_state[node]

            # Sinks drain and absorb — vehicles leave the network
            if roles.get(node) == "sink":
                delta[node] -= own_load * SINK_DRAIN
                continue

            # Flow only downhill (higher → lower congestion)
            eligible = [nb for nb in neighbours
                        if nb in nodes and _spider_state.get(nb, 0) < own_load]
            if not eligible:
                continue

            load_to_push = own_load * FLOW_RATE
            gaps         = [own_load - _spider_state.get(nb, 0) for nb in eligible]
            total_gap    = sum(gaps)

            for nb, gap in zip(eligible, gaps):
                share = (gap / total_gap) * load_to_push
                delta[node] -= share
                delta[nb]   += share

        # Apply + noise + clamp
        new_state = {}
        for node in nodes:
            raw = _spider_state[node] + delta[node] + random.uniform(-NOISE, NOISE)
            lo  = 15.0 if roles.get(node) == "generator" else 2.0
            new_state[node] = max(lo, min(90.0, raw))

        # Soft conservation rescale
        total = sum(new_state.values())
        if total > 0 and abs(total - TOTAL_VEHICLE_POOL) / TOTAL_VEHICLE_POOL > 0.30:
            scale = TOTAL_VEHICLE_POOL / total
            new_state = {n: max(2.0, min(90.0, v * scale)) for n, v in new_state.items()}

        _spider_state.update(new_state)
        result = {n: int(round(v)) for n, v in new_state.items()}

    try:
        log_spiderweb(result)
    except Exception as e:
        log.warning("Spiderweb DB log error: %s", e)

    return jsonify(result)



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


@app.route("/api/spiderweb-reset", methods=["POST"])
def spiderweb_reset():
    data  = request.get_json()
    level = data.get("level", "low")
    seed_ranges = {"low": (5, 20), "moderate": (30, 55), "high": (60, 85)}
    lo, hi = seed_ranges.get(level, (5, 20))
    with _spider_lock:
        for node in _spider_state:
            _spider_state[node] = random.uniform(lo, hi)
    log.info("Spiderweb reset — level: %s", level)
    return jsonify({"status": "reset", "level": level})


# ── Run ────────────────────────────────────────────────
if __name__ == "__main__":
    socketio.run(app, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
