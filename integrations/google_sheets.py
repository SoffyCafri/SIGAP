import os
from pathlib import Path

from django.conf import settings
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
DEFAULT_CREDENTIALS_PATH = Path('/run/secrets/google_service_account.json')

def get_credentials_path():
    configured_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if configured_path:
        p = Path(configured_path)
        if p.is_file():
            return p

    candidates = (
        DEFAULT_CREDENTIALS_PATH,
        Path('/app/credentials/google-sheets.json'),  # <--- Ruta real en el contenedor
        settings.BASE_DIR / 'credentials' / 'google-sheets.json',  # <--- Ruta local en disco
    )
    return next((path for path in candidates if path.is_file()), candidates[0])


def get_sheets_service():
    credentials_path = get_credentials_path()
    if not credentials_path.is_file():
        raise FileNotFoundError(
            'No se encontró el archivo de credenciales de Google Sheets en '
            f'{credentials_path}. Configura GOOGLE_APPLICATION_CREDENTIALS.'
        )

    credentials = Credentials.from_service_account_file(
        credentials_path,
        scopes=SCOPES,
    )
    return build('sheets', 'v4', credentials=credentials)
