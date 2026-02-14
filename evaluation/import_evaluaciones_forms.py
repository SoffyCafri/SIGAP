from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from django.utils.timezone import make_aware
from datetime import datetime

from projects.models import Proyecto
from evaluation.models import Evaluaciones
from django.conf import settings
from people.models import Evaluador 
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
    if not os.path.exists(RUTA_CREDENCIALES):
        # Error en caso de que no se encuentre las credenciales 
        raise FileNotFoundError(f"❌ CRÍTICO: No se encontró el archivo de credenciales en: {RUTA_CREDENCIALES}")
    
    try:
        creds = Credentials.from_service_account_file(RUTA_CREDENCIALES, scopes=SCOPES)
    except Exception as e:
        raise Exception(f"El archivo existe pero las credenciales son inválidas: {e}")
    
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()

    try:
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME
        ).execute()
    except Exception as e:
        raise Exception(f"Error conectando con Google Sheets: {e}")

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

        # ================= EVALUADOR =================
        # Buscamos la columna del correo. Google Forms suele llamarla así:
        email_col = headers_normalizados.get("DIRECCIÓN DE CORREO ELECTRÓNICO")
        
        # Si no la encuentra por ese nombre, intenta buscar 'EMAIL ADDRESS' o similar
        if not email_col:
             email_col = headers_normalizados.get("EMAIL ADDRESS")

        email_evaluador = data.get(email_col)

        if not email_evaluador:
            print(f"⚠ Registro sin correo de evaluador. Folio: {folio}")
            continue # Si no hay correo en el excel, bateamos el registro.

        try:
            # Buscamos al evaluador en la BD por su correo
            evaluador_obj = Evaluador.objects.get(correo_evaluador=email_evaluador.strip())
        except Evaluador.DoesNotExist:
            print(f"⛔ Evaluador no registrado en sistema: {email_evaluador}. Se omite la evaluación.")
            continue # Bateamos el registro si el evaluador no existe en el sistema.

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
            evaluador=evaluador_obj,
            tipo_revision=tipo_revision,
            resolutivo="PENDIENTE",
            observaciones=observaciones,
            fecha_evaluacion=fecha
        )

        count += 1

    return count