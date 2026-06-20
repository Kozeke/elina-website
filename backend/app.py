import os
import smtplib
import urllib.request
from email.message import EmailMessage
from contextlib import asynccontextmanager

import stripe
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
ENDPOINT_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

GMAIL_USER = os.environ["GMAIL_USER"]               # e.g. you@gmail.com
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]  # 16-char App Password

# Google Drive file ID extracted from the shareable link
GDRIVE_FILE_ID = os.environ.get("GDRIVE_FILE_ID", "")

# Local path where the PDF will be saved after downloading from Google Drive
BOOK_PATH = "/tmp/book.pdf"

# Direct download URL for a publicly shared Google Drive file
GDRIVE_DOWNLOAD_URL = f"https://drive.google.com/uc?export=download&id={GDRIVE_FILE_ID}"


def download_book() -> None:
    """Download the book PDF from Google Drive to the local /tmp directory at startup."""
    if not GDRIVE_FILE_ID:
        print("WARNING: GDRIVE_FILE_ID is not set — book will not be available.")
        return
    print(f"Downloading book from Google Drive (file id: {GDRIVE_FILE_ID})...")
    urllib.request.urlretrieve(GDRIVE_DOWNLOAD_URL, BOOK_PATH)
    print(f"Book downloaded successfully to {BOOK_PATH}.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Download the book PDF from Google Drive before the server starts accepting requests
    download_book()
    yield


app = FastAPI(lifespan=lifespan)


def send_book(to_email: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = "Ваша книга"
    msg["From"] = GMAIL_USER
    msg["To"] = to_email
    msg.set_content("Спасибо за покупку! Книга во вложении.")

    with open(BOOK_PATH, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="pdf",
            filename="book.pdf",
        )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)


@app.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, ENDPOINT_SECRET)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"].to_dict()
        customer_email = (
            session.get("customer_details", {}).get("email")
            or session.get("customer_email")
        )
        if customer_email:
            send_book(customer_email)

    return JSONResponse({"success": True})


@app.get("/health")
async def health():
    return {"status": "ok"}