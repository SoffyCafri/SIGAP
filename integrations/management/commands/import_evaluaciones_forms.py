from django.core.management.base import BaseCommand
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from django.utils.timezone import make_aware
from datetime import datetime

from projects.models import Proyecto
from people.models import Evaluador
from evaluation.models import Evaluaciones

SPREADSHEET_ID = "1LJKWlgLL9qi1a8C_KoiEB65ZCJiW2mxze0Aj5Sa_K7c"
RANGE_NAME = "Respuestas de formulario 1!A:Z"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

def normalizar(texto):
    return texto.strip().upper() if texto else ""

class Command(BaseCommand):
    help = "Importa evaluaciones desde Google Forms"

    def handle(self, *args, **kwargs):
        creds = Credentials.from_service_account_file(
            "/app/SIGAP/credentials/google_service_account.json",
            scopes=SCOPES
        )
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()

        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME
        ).execute()

        rows = result.get("values", [])
        headers = rows[0]
        data_rows = rows[1:]

        for row in data_rows:
            data = dict(zip(headers, row))

            # 🔹 FOLIO
            folio = data.get("Ingresa el folio de tu proyecto asignado")
            if not folio:
                continue

            try:
                proyecto = Proyecto.objects.get(folio=folio)
            except Proyecto.DoesNotExist:
                continue

            # 🔹 VECES EVALUADO (NO se guarda, solo informativo)
            veces = data.get("Selecciona cuantas veces has evaluado este proyecto")

            # 🔹 TIPO DE CORRECCIÓN
            tipo_raw = normalizar(data.get("¿La corrección es de fondo o forma?"))

            tipo_map = {
                "FONDO": "FONDO",
                "FORMA": "FORMA",
                "NO APLICA": "FINAL"
            }
            tipo_revision = tipo_map.get(tipo_raw, "FORMA")

            # 🔹 OBSERVACIONES
            observaciones = normalizar(data.get("Observaciones"))

            # 🔹 FECHA
            fecha_str = data.get("Marca temporal")
            fecha = make_aware(datetime.strptime(fecha_str, "%d/%m/%Y %H:%M:%S"))

            # 🔹 EVALUADOR (opcional)
            evaluador = None

            # GUARDAR HISTÓRICO
            Evaluaciones.objects.create(
                proyecto=proyecto,
                evaluador=evaluador,
                tipo_revision=tipo_revision,
                resolutivo="PENDIENTE",
                observaciones=observaciones,
                fecha_evaluacion=fecha
            )
