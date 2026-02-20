import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask import jsonify, Response
from services.traffic_service import get_traffic_status
from services.video_service import generate_video_stream

# -----------------------------
# App setup
# -----------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "../frontend/templates"),
    static_folder=os.path.join(BASE_DIR, "../frontend/static")
)

app.secret_key = "THIS_IS_A_FIXED_SECRET_KEY_12345"

# -----------------------------
# Global Detection Mode
# -----------------------------
CURRENT_MODE = "simulation"  # default mode

# -----------------------------
# Users
# -----------------------------

USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "user": {"password": "user123", "role": "user"},
}

# -----------------------------
# Routes
# -----------------------------
@app.route("/upload-video", methods=["POST"])
def upload_video():
    file = request.files.get("video")

    if not file:
        return jsonify({"status": "error"})

    upload_path = os.path.join(BASE_DIR, "uploaded_video.mp4")
    file.save(upload_path)

    return jsonify({"status": "success"})

@app.route('/video_feed')
def video_feed():
    return Response(
        generate_video_stream(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username in USERS and USERS[username]["password"] == password:
            session.clear()
            session["username"] = username
            session["role"] = USERS[username]["role"]

            if session["role"] == "admin":
                return redirect(url_for("admin"))
            else:
                return redirect(url_for("user"))

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


# -----------------------------
# Mode Switching API
# -----------------------------

@app.route("/set-mode/<mode>")
def set_mode(mode):
    global CURRENT_MODE, VIDEO_UPLOADED

    CURRENT_MODE = mode

    if mode == "simulation":
        VIDEO_UPLOADED = False

        video_path = os.path.join(BASE_DIR, "uploaded_video.mp4")

        if os.path.exists(video_path):
            os.remove(video_path)   # 🔥 Delete video automatically

    return jsonify({"current_mode": CURRENT_MODE})


# -----------------------------
# Traffic API
# -----------------------------

@app.route("/api/traffic-status")
def traffic_status():
    data = get_traffic_status(CURRENT_MODE)
    return jsonify(data)


# -----------------------------
# Run
# -----------------------------

if __name__ == "__main__":
    app.run(debug=False)
