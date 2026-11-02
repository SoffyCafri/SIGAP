from pathlib import Path

from django.conf import settings
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
GOOGLE_CREDENTIALS_PATH = (
    Path(settings.BASE_DIR) / 'credentials' / 'google-sheets.json'
)


def get_sheets_service():
    if not GOOGLE_CREDENTIALS_PATH.is_file():
        raise FileNotFoundError(
            'No se encontró el archivo de credenciales de Google Sheets en '
            f'{GOOGLE_CREDENTIALS_PATH}.'
        )

    credentials = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_PATH,
        scopes=SCOPES,
    )
    return build('sheets', 'v4', credentials=credentials)
