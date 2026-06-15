import os
import random
import re
import sqlite3
import time

from werkzeug.security import check_password_hash, generate_password_hash

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from groq import Groq


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

if not app.secret_key:
    if os.getenv("FLASK_ENV") == "production":
        raise RuntimeError("SECRET_KEY must be set in production.")
    app.secret_key = "dev-secret-key-change-me"

if os.getenv("FLASK_ENV") == "production":
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=True,
    )

SYSTEM_INSTRUCTION = (
    "You are Mutthi, a compassionate and emotionally intelligent AI therapy companion. "
    "Create a safe, calm, non-judgmental space where the user feels heard and respected. "
    "Respond like a supportive therapist: validate emotions, reflect the user's feelings, ask one thoughtful "
    "open-ended question when helpful, and offer gentle coping strategies such as grounding, breathing, "
    "journaling, reframing, or breaking problems into smaller steps. "
    "Keep replies short: usually 2 to 5 sentences total, in 1 or 2 brief paragraphs. "
    "Avoid long explanations, lists, and lectures unless the user clearly asks for detail. "
    "Do not diagnose, shame, argue, or give harsh advice. Do not claim to be a licensed therapist, doctor, "
    "or emergency service. Encourage professional support when the concern is serious, persistent, medical, "
    "or beyond self-help. "
    "If the user mentions self-harm, suicide, abuse, violence, immediate danger, or feeling unable to stay safe, "
    "respond with extra care: acknowledge their pain, encourage them to contact local emergency services or a "
    "trusted person immediately, and suggest crisis support right away. "
    "For every response, prioritize empathy, safety, hope, and practical next steps."
)

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "10"))
DATABASE = os.getenv("DATABASE", "mindwell.db")

_groq_client = None


def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    db = get_db()
    try:
        db.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        db.commit()
    finally:
        db.close()


init_db()


def get_groq_client():
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set.")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


def build_messages(history, user_message):
    messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
    messages.extend(
        {"role": msg["role"], "content": msg["content"]}
        for msg in history
        if msg.get("role") in {"user", "assistant"} and msg.get("content")
    )
    messages.append({"role": "user", "content": user_message})
    return messages


def generate_reply(history, user_message):
    client = get_groq_client()
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=build_messages(history, user_message),
        temperature=0.7,
        max_completion_tokens=90,
    )
    return completion.choices[0].message.content.strip()


def current_user():
    return session.get("user")


def sanitize_next_url(next_url):
    if not next_url or not next_url.startswith("/"):
        return url_for("chat_page")
    return next_url


def login_required_response():
    if request.path.startswith("/api/"):
        return jsonify({"error": "Please log in to use chat."}), 401
    next_url = request.full_path.rstrip("?")
    return redirect(url_for("login", next=next_url))


def is_valid_email(email):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok"})


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        if not is_valid_email(email):
            flash("Please enter a valid email address.", "error")
            return render_template("signup.html", email=email)

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("signup.html", email=email)

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("signup.html", email=email)

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, generate_password_hash(password)),
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("An account with this email already exists.", "error")
            return render_template("signup.html", email=email)
        finally:
            db.close()

        session["user"] = {
            "id": email,
            "name": email.split("@")[0],
            "email": email,
        }
        session.modified = True
        return redirect(url_for("chat_page"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    next_url = sanitize_next_url(request.args.get("next") or request.form.get("next"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not is_valid_email(email):
            flash("Please enter a valid email address.", "error")
            return render_template("login.html", next_url=next_url, email=email)

        db = get_db()
        try:
            row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        finally:
            db.close()

        if not row or not check_password_hash(row["password_hash"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html", next_url=next_url, email=email)

        session["user"] = {
            "id": email,
            "name": email.split("@")[0],
            "email": email,
        }
        session.modified = True
        return redirect(next_url)

    return render_template("login.html", next_url=next_url)


@app.route("/chat")
def chat_page():
    if not current_user():
        return login_required_response()
    return render_template("chat.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("chat_history", None)
    session.pop("pending_login", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/api/chat", methods=["POST"])
def api_chat():
    if not current_user():
        return login_required_response()

    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    history = session.get("chat_history", [])

    try:
        bot_reply = generate_reply(history, user_message)
    except Exception as exc:
        print(f"Groq API Error: {exc}")
        return jsonify({"error": "The AI is currently unavailable. Please try again later."}), 500

    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": bot_reply})
    session["chat_history"] = history[-MAX_HISTORY_MESSAGES:]
    session.modified = True

    return jsonify({"response": bot_reply})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_ENV") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug)
