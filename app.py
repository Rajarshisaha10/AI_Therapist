import os
import random
import re
import smtplib
import time
from email.message import EmailMessage

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
OTP_EXPIRY_SECONDS = int(os.getenv("OTP_EXPIRY_SECONDS", "300"))
SHOW_OTP_IN_FLASH = os.getenv("SHOW_OTP_IN_FLASH", "true").lower() == "true"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USERNAME = os.getenv("EMAIL_USERNAME")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM") or EMAIL_USERNAME

_groq_client = None


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
        return jsonify({"error": "Please log in with email and OTP to use chat."}), 401
    next_url = request.full_path.rstrip("?")
    return redirect(url_for("login", next=next_url))


def is_valid_email(email):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def email_configured():
    return (
        EMAIL_HOST
        and EMAIL_PORT
        and EMAIL_USERNAME
        and EMAIL_PASSWORD
        and EMAIL_FROM
        and not EMAIL_USERNAME.startswith("your_")
        and not EMAIL_PASSWORD.startswith("your_")
    )


def send_otp_to_email(email, otp):
    if not email_configured():
        print(f"OTP for {email}: {otp}")
        return "console"

    message = EmailMessage()
    message["Subject"] = "Your Seren verification code"
    message["From"] = EMAIL_FROM
    message["To"] = email
    message.set_content(
        f"Your Seren verification OTP is {otp}.\n\n"
        f"It expires in {OTP_EXPIRY_SECONDS // 60} minutes."
    )

    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as smtp:
        smtp.starttls()
        smtp.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        smtp.send_message(message)

    print(f"OTP email sent to {email}")
    return "email"


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok"})


@app.route("/login", methods=["GET", "POST"])
def login():
    next_url = sanitize_next_url(request.args.get("next") or request.form.get("next"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()

        if not is_valid_email(email):
            flash("Please enter a valid email address.", "error")
            return render_template("login.html", next_url=next_url, email=email)

        otp = f"{random.randint(0, 999999):06d}"
        session["pending_login"] = {
            "email": email,
            "otp": otp,
            "expires_at": int(time.time()) + OTP_EXPIRY_SECONDS,
            "next_url": next_url,
        }
        session.modified = True

        delivery_method = send_otp_to_email(email, otp)
        if SHOW_OTP_IN_FLASH or delivery_method == "console":
            flash(f"Development OTP: {otp}", "info")
        else:
            flash("We sent an OTP to your email.", "info")
        return redirect(url_for("verify_otp"))

    return render_template("login.html", next_url=next_url)


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    pending_login = session.get("pending_login")
    if not pending_login:
        flash("Start by entering your email.", "info")
        return redirect(url_for("login"))

    if request.method == "POST":
        submitted_otp = (request.form.get("otp") or "").strip()
        if int(time.time()) > pending_login.get("expires_at", 0):
            session.pop("pending_login", None)
            flash("That OTP expired. Please request a new one.", "error")
            return redirect(url_for("login"))

        if submitted_otp != pending_login.get("otp"):
            flash("Invalid OTP. Please try again.", "error")
            return render_template("verify_otp.html", email=pending_login.get("email"))

        email = pending_login["email"]
        session["user"] = {
            "id": email,
            "name": email.split("@")[0],
            "email": email,
        }
        next_url = sanitize_next_url(pending_login.get("next_url"))
        session.pop("pending_login", None)
        session.modified = True
        return redirect(next_url)

    return render_template("verify_otp.html", email=pending_login.get("email"))


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
