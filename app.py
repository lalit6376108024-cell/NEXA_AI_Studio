
import os
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, send_from_directory, abort
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "instance"))
UPLOAD_DIR = DATA_DIR / "uploads"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "development-key-change-before-deployment"
)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

DB_PATH = DATA_DIR / "nexa.db"
ALLOWED_EXTENSIONS = {"mp4", "mov", "webm", "m4v", "avi"}

PRESETS = {
    "Viral Reel": {
        "pace": "Fast cuts and a strong opening hook",
        "format": "9:16 vertical",
        "look": "High contrast and crisp details"
    },
    "Cinematic": {
        "pace": "Deliberate cuts and breathing room",
        "format": "16:9 widescreen",
        "look": "Soft contrast and cinematic tones"
    },
    "Velocity / Beat Sync": {
        "pace": "Short cuts designed around music beats",
        "format": "9:16 vertical",
        "look": "Energetic contrast and motion"
    },
    "Motivation": {
        "pace": "Build from calm to powerful",
        "format": "9:16 vertical",
        "look": "Warm highlights and deep shadows"
    },
    "AI Story": {
        "pace": "Hook, setup, reveal, memorable ending",
        "format": "9:16 or 16:9",
        "look": "Consistent storytelling mood"
    },
    "Retro / VHS": {
        "pace": "Playful nostalgic rhythm",
        "format": "4:3 or 9:16",
        "look": "Retro-inspired color and grain"
    },
    "Clean Creator": {
        "pace": "Clear edits and natural pauses",
        "format": "9:16 or 16:9",
        "look": "Natural colors and skin tones"
    },
    "Motion Graphics": {
        "pace": "Graphic-led rhythm and transitions",
        "format": "9:16 or 16:9",
        "look": "Bold, consistent colors"
    }
}


def connect_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connect_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                preset TEXT NOT NULL,
                brief TEXT DEFAULT '',
                filename TEXT DEFAULT '',
                original_name TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)


init_db()


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def make_plan(preset, brief):
    style = PRESETS.get(preset, PRESETS["Viral Reel"])

    plan = [
        "Find the strongest opening moment.",
        "Remove unnecessary pauses and dead space.",
        f"Editing pace: {style['pace']}.",
        f"Target format: {style['format']}.",
        f"Visual direction: {style['look']}.",
        "Check audio levels and review the final export."
    ]

    if brief:
        plan.insert(1, f"Creative brief: {brief[:400]}")

    return plan


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        title = request.form.get(
            "title", "Untitled project"
        ).strip()[:100] or "Untitled project"

        preset = request.form.get("preset", "Viral Reel")
        if preset not in PRESETS:
            preset = "Viral Reel"

        brief = request.form.get("brief", "").strip()[:2000]
        upload = request.files.get("video")

        filename = ""
        original_name = ""

        if upload and upload.filename:
            if not allowed_file(upload.filename):
                flash(
                    "Upload an MP4, MOV, WEBM, M4V, or AVI video.",
                    "error"
                )
                return redirect(url_for("index"))

            original_name = Path(upload.filename).name
            extension = Path(original_name).suffix.lower()
            filename = f"{uuid.uuid4().hex}{extension}"
            upload.save(UPLOAD_DIR / filename)

        with connect_db() as db:
            cursor = db.execute("""
                INSERT INTO projects
                (title, preset, brief, filename, original_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                title,
                preset,
                brief,
                filename,
                original_name,
                datetime.now().strftime("%Y-%m-%d %H:%M")
            ))
            project_id = cursor.lastrowid

        flash("Your project and editing blueprint have been saved.", "success")
        return redirect(url_for("project", project_id=project_id))

    with connect_db() as db:
        projects = db.execute(
            "SELECT * FROM projects ORDER BY id DESC LIMIT 12"
        ).fetchall()

    return render_template(
        "index.html",
        projects=projects,
        presets=PRESETS
    )


@app.route("/project/<int:project_id>")
def project(project_id):
    with connect_db() as db:
        item = db.execute(
            "SELECT * FROM projects WHERE id = ?",
            (project_id,)
        ).fetchone()

    if item is None:
        abort(404)

    return render_template(
        "project.html",
        project=item,
        presets=PRESETS,
        plan=make_plan(item["preset"], item["brief"])
    )


@app.route("/uploads/<path:filename>")
def uploaded_video(filename):
    if Path(filename).name != filename:
        abort(404)

    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/health")
def health():
    return {"status": "ok", "app": "NEXA AI Video Studio"}


@app.errorhandler(413)
def upload_too_large(error):
    return "Video exceeds the 500 MB upload limit.", 413


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
