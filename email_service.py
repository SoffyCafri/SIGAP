import os
import base64

from email.message import EmailMessage

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def enviar_correo_gmail(asunto, mensaje, destinatarios):

    credentials = Credentials(
        token=None,
        refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GMAIL_CLIENT_ID"],
        client_secret=os.environ["GMAIL_CLIENT_SECRET"],
        scopes=SCOPES
    )

    credentials.refresh(Request())

    service = build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False
    )

    email = EmailMessage()
    email["To"] = ", ".join(destinatarios)
    email["From"] = os.environ["GMAIL_SENDER_EMAIL"]
    email["Subject"] = asunto
    email.set_content(mensaje)

    raw_message = base64.urlsafe_b64encode(
        email.as_bytes()
    ).decode()

    response = service.users().messages().send(
        userId="me",
        body={"raw": raw_message}
    ).execute()

    return response