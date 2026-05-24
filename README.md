# AI Therapist

Flask chat app with Groq responses and Twilio SMS OTP login.

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create `.env` from `.env.example` and fill in your secrets.
4. Run locally:

   ```bash
   python app.py
   ```

## Render Deployment

Use these settings if deploying manually on Render:

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Runtime: Python 3.11

Add the environment variables from `.env.example` in the Render dashboard. Do not upload `.env`.

For Twilio SMS sending, this app does not need a Twilio webhook URL. Use your Render app URL if Twilio asks for a website or app URL.
