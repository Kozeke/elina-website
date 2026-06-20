import os
import smtplib
from email.message import EmailMessage

import stripe
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse


stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
ENDPOINT_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

GMAIL_USER = os.environ["GMAIL_USER"]               # e.g. you@gmail.com
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]  # 16-char App Password

# Google Drive file ID extracted from the shareable link
GDRIVE_FILE_ID = os.environ.get("GDRIVE_FILE_ID", "")

app = FastAPI()


def send_book(to_email: str) -> None:
    """Send the customer an email containing a direct Google Drive download link instead of an attachment."""
    # Google Drive shareable link for the customer to download the book
    book_link = f"https://drive.google.com/file/d/{GDRIVE_FILE_ID}/view?usp=sharing"

    msg = EmailMessage()
    msg["Subject"] = "Ваша книга"
    msg["From"] = GMAIL_USER
    msg["To"] = to_email
    msg.set_content(
        f"Спасибо за покупку!\n\n"
        f"Вы можете скачать вашу книгу по ссылке:\n{book_link}\n\n"
        f"С уважением,\nElina"
    )

    # Send plain email with a link — avoids Gmail's 25 MB attachment size limit
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