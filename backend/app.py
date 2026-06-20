import os
import smtplib
from email.message import EmailMessage

import stripe
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI()

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
ENDPOINT_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

GMAIL_USER = os.environ["GMAIL_USER"]               # e.g. you@gmail.com
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]  # 16-char App Password
BOOK_PATH = os.environ.get("BOOK_PATH", "book.pdf")    # path to your PDF on the server


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
        session = event["data"]["object"]
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