# AI Therapist

Flask chat app with Groq responses and Gmail email OTP login.

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

For Gmail OTP sending, use a Google App Password for `EMAIL_PASSWORD`. Do not use your normal Gmail password.

To create a Gmail App Password:

1. Turn on 2-Step Verification in your Google account.
2. Open Google Account > Security > App passwords.
3. Create an app password for this project.
4. Use the generated 16-character password as `EMAIL_PASSWORD`.
