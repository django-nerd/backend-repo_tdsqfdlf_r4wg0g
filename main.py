import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from database import db, create_document
import smtplib
from email.mime.text import MIMEText

app = FastAPI(title="KMA Global API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ContactSubmission(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    phone: Optional[str] = None
    business: Optional[str] = None
    budget: Optional[str] = None
    description: str = Field(..., min_length=10)


@app.get("/")
def read_root():
    return {"message": "KMA Global API running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/test")
def test_database():
    """Test endpoint to check database connectivity and envs"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else (os.getenv("DATABASE_NAME") or "Unknown")
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"

    return response


@app.post("/api/contact")
def submit_contact(payload: ContactSubmission):
    """Accept contact form submissions, store to DB, send optional confirmation email."""
    # Persist to database
    try:
        doc_id = create_document("contactsubmission", payload)
    except Exception as e:
        # Still allow without DB, but report failure
        doc_id = None

    email_result = _send_confirmation_email(payload)

    return {
        "ok": True,
        "id": doc_id,
        "email": email_result,
        "message": "Thanks. We\u2019ve received your details and will be in touch shortly."
    }


def _send_confirmation_email(payload: ContactSubmission):
    """Send confirmation email via SMTP if env vars are configured.
    Returns a dict with status and reason.
    """
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    from_email = os.getenv("SMTP_FROM", user or "")
    to_email = payload.email

    if not (host and user and password and from_email):
        return {
            "sent": False,
            "reason": "SMTP not configured",
        }

    subject = "KMA Global – We\u2019ve received your enquiry"
    body = (
        f"Hi {payload.name},\n\n"
        "Thanks for reaching out to KMA Global. We\u2019ve received your message and a consultant will get back to you shortly.\n\n"
        "Summary of your submission:\n"
        f"– Email: {payload.email}\n"
        f"– Phone: {payload.phone or 'N/A'}\n"
        f"– Business: {payload.business or 'N/A'}\n"
        f"– Budget: {payload.budget or 'N/A'}\n\n"
        "If you\u2019d like to book a call now, you can use our scheduling link: https://calendly.com/\n\n"
        "Best regards,\nKMA Global"
    )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(from_email, [to_email], msg.as_string())
        return {"sent": True}
    except Exception as e:
        return {"sent": False, "reason": str(e)[:120]}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
