
import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask import jsonify, Response

from services.traffic_service import get_traffic_status
from services.video_service import detect_vehicles_from_video
from services.video_service import generate_video_stream
from flask import Response
from flask import request

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

CURRENT_MODE = "simulation"

# -----------------------------
# Users
# -----------------------------

USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "user": {"password": "user123", "role": "user"},
}

from flask import send_file
import os

@app.route("/get-video")
def get_video():
    video_path = os.path.join(os.path.dirname(__file__), "uploaded_video.mp4")

    if not os.path.exists(video_path):
        return "No video", 404

    return send_file(video_path)

################################
import random
nodes = {
    "A":10,
    "B":20,
    "C":15,
    "D":5,
    "E":8
}

graph = {
    "A":["B","D"],
    "B":["A","C","E"],
    "C":["B"],
    "D":["A","E"],
    "E":["B","D"]
}

def compute_influence(node):
    influence = 0
    for neighbor in graph[node]:
        influence += nodes[neighbor] * 0.4
    return nodes[node] + influence

@app.route("/api/spiderweb-data", methods=["POST"])
def spiderweb_data():

    data = request.get_json()

    nodes = data.get("nodes", {})
    edges = data.get("edges", {})

    result = {}

    for node in nodes:
        own = random.randint(5,30)

        influence = 0
        for neighbor in edges.get(node, []):
            influence += random.randint(5,20) * 0.4

        result[node] = int(own + influence)

    return result
######################################################

@app.route("/video_feed")
def video_feed():

    video_path = os.path.join(os.path.dirname(__file__), "uploaded_video.mp4")

    return Response(
        generate_video_stream(video_path),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )
# -----------------------------
# Upload Video
# -----------------------------

@app.route("/upload-video", methods=["POST"])
def upload_video():

    video = request.files["video"]

    # 🔥 FORCE SAVE IN BACKEND FOLDER
    video_path = os.path.join(os.path.dirname(__file__), "uploaded_video.mp4")

    video.save(video_path)

    print("✅ Video saved at:", video_path)

    return {"status": "uploaded"}




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
# Mode Switching
# -----------------------------

@app.route("/set-mode/<mode>")
def set_mode(mode):

    global CURRENT_MODE

    if mode not in ["simulation", "video"]:
        return jsonify({"error": "Invalid mode"}), 400

    CURRENT_MODE = mode

    # 👉 If switching to simulation → delete uploaded video
    if mode == "simulation":

        video_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploaded_video.mp4")

        if os.path.exists(video_path):
            try:
                os.remove(video_path)
                print("✅ Uploaded video deleted")
            except Exception as e:
                print("❌ Error deleting video:", e)

    return jsonify({"current_mode": CURRENT_MODE})


# -----------------------------
# Traffic API
# -----------------------------

@app.route('/api/traffic-status')
def traffic_status():
    return get_traffic_status(CURRENT_MODE)


# -----------------------------
# Run App
# -----------------------------

if __name__ == "__main__":
    app.run(debug=True)
