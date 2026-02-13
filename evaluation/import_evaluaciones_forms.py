from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from django.utils.timezone import make_aware
from datetime import datetime

from projects.models import Proyecto
from evaluation.models import Evaluaciones
from django.conf import settings
import os

# ================= GOOGLE SHEETS CONFIG =================
SPREADSHEET_ID = "1LJKWlgLL9qi1a8C_KoiEB65ZCJiW2mxze0Aj5Sa_K7c"
RANGE_NAME = "Respuestas de formulario 1!A:Z"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

RUTA_CREDENCIALES = os.path.join(
    settings.BASE_DIR,
    "google_service_account.json.json"
)


# ================= UTILIDADES =================
def normalizar(texto):
    return texto.strip().upper() if texto else ""


# ================= IMPORTADOR PRINCIPAL =================
def importar_evaluaciones_forms():
    creds = Credentials.from_service_account_file(RUTA_CREDENCIALES, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()

    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME
    ).execute()

    rows = result.get("values", [])
    if not rows:
        return 0

    
    headers = [h.strip() for h in rows[0]]
    headers_normalizados = {h.strip().upper(): h for h in headers}

    data_rows = rows[1:]
    count = 0

    for row in data_rows:
        if len(row) < len(headers):
            row += [None] * (len(headers) - len(row))

        data = dict(zip(headers, row))

        # ================= FOLIO =================
        folio_col = headers_normalizados.get("INGRESA EL FOLIO DE TU PROYECTO ASIGNADO")
        if not folio_col:
            continue

        folio = data.get(folio_col)
        if not folio:
            continue

        try:
            proyecto = Proyecto.objects.get(folio=folio.strip())
        except Proyecto.DoesNotExist:
            continue

        # ================= TIPO REVISION =================
        tipo_col = headers_normalizados.get("¿LA CORRECCIÓN ES DE FONDO O FORMA?")
        tipo_raw = normalizar(data.get(tipo_col))

        tipo_map = {
            "FONDO": "FONDO",
            "FORMA": "FORMA",
            "NO APLICA": "FINAL"
        }

        tipo_revision = tipo_map.get(tipo_raw, "FORMA")

        # ================= OBSERVACIONES =================
        obs_col = headers_normalizados.get("OBSERVACIONES")
        observaciones = data.get(obs_col, "")

        # ================= FECHA =================
        fecha_col = headers_normalizados.get("MARCA TEMPORAL")
        fecha_str = data.get(fecha_col)

        if fecha_str:
            try:
                fecha = make_aware(datetime.strptime(fecha_str, "%d/%m/%Y %H:%M:%S"))
            except:
                fecha = make_aware(datetime.now())
        else:
            fecha = make_aware(datetime.now())

        
        if Evaluaciones.objects.filter(
            proyecto=proyecto,
            fecha_evaluacion=fecha
        ).exists():
            continue

        Evaluaciones.objects.create(
            proyecto=proyecto,
            evaluador=None,
            tipo_revision=tipo_revision,
            resolutivo="PENDIENTE",
            observaciones=observaciones,
            fecha_evaluacion=fecha
        )

        count += 1

    return count