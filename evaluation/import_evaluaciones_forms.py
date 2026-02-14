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

# Ajusta el nombre si tu archivo tiene doble .json o no
RUTA_CREDENCIALES = os.path.join(
    settings.BASE_DIR,
    "google_service_account.json.json" 
)


# ================= UTILIDADES =================
def normalizar(texto):
    return texto.strip().upper() if texto else ""


# ================= IMPORTADOR PRINCIPAL =================
def importar_evaluaciones_forms():
    # 1. Validación de Archivo de Credenciales
    if not os.path.exists(RUTA_CREDENCIALES):
        raise FileNotFoundError(f"❌ CRÍTICO: No se encontró el archivo de credenciales en: {RUTA_CREDENCIALES}")
    
    try:
        creds = Credentials.from_service_account_file(RUTA_CREDENCIALES, scopes=SCOPES)
    except Exception as e:
        raise Exception(f"El archivo existe pero las credenciales son inválidas: {e}")
    
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()

    # 2. Conexión a Google Sheets
    try:
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME
        ).execute()
    except Exception as e:
        raise Exception(f"Error conectando con Google Sheets: {e}")

    rows = result.get("values", [])
    
    # IMPORTANTE: Si no hay filas, devolvemos 0 éxitos y lista vacía de errores
    if not rows:
        return 0, []

    # 3. Procesamiento de Headers
    headers = [h.strip() for h in rows[0]]
    headers_normalizados = {h.strip().upper(): h for h in headers}

    data_rows = rows[1:]
    count = 0
    errores = [] # Lista para acumular los reportes de filas ignoradas

    for i, row in enumerate(data_rows):
        # Número de fila humano (Excel empieza en 1, headers es 1, data empieza en 2)
        num_fila_excel = i + 2 

        if len(row) < len(headers):
            row += [None] * (len(headers) - len(row))

        data = dict(zip(headers, row))

        # ================= A. FOLIO =================
        folio_col = headers_normalizados.get("INGRESA EL FOLIO DE TU PROYECTO ASIGNADO")
        if not folio_col: 
            # Si no existe la columna, es un error grave de estructura del Excel
            continue 

        folio = data.get(folio_col)
        if not folio:
            # Si la fila no tiene folio, la ignoramos sin error (fila vacía)
            continue

        try:
            proyecto = Proyecto.objects.get(folio=folio.strip())
        except Proyecto.DoesNotExist:
            errores.append(f"Fila {num_fila_excel}: Folio '{folio}' no encontrado en el sistema.")
            continue

        # ================= B. EVALUADOR (Lógica de Correo) =================
        email_col = headers_normalizados.get("DIRECCIÓN DE CORREO ELECTRÓNICO") or headers_normalizados.get("EMAIL ADDRESS")
        email_evaluador = data.get(email_col)

        if not email_evaluador:
            errores.append(f"Fila {num_fila_excel}: Registro sin correo electrónico (Folio {folio}).")
            continue

        try:
            # Buscamos al evaluador por correo (usamos iexact por si hay mayúsculas/minúsculas diferentes)
            evaluador_obj = Evaluador.objects.get(correo_evaluador__iexact=email_evaluador.strip())
        except Evaluador.DoesNotExist:
            # AQUÍ BATEAMOS EL REGISTRO
            errores.append(f"Fila {num_fila_excel}: El evaluador '{email_evaluador}' no existe en la base de datos.")
            continue 

        # ================= C. OTROS DATOS =================
        tipo_col = headers_normalizados.get("¿LA CORRECCIÓN ES DE FONDO O FORMA?")
        tipo_raw = normalizar(data.get(tipo_col))

        tipo_map = {
            "FONDO": "FONDO",
            "FORMA": "FORMA",
            "NO APLICA": "FINAL"
        }
        tipo_revision = tipo_map.get(tipo_raw, "FORMA")

        obs_col = headers_normalizados.get("OBSERVACIONES")
        observaciones = data.get(obs_col, "")

        fecha_col = headers_normalizados.get("MARCA TEMPORAL")
        fecha_str = data.get(fecha_col)

        if fecha_str:
            try:
                fecha = make_aware(datetime.strptime(fecha_str, "%d/%m/%Y %H:%M:%S"))
            except:
                fecha = make_aware(datetime.now())
        else:
            fecha = make_aware(datetime.now())

        
        # ================= D. DUPLICADOS Y GUARDADO =================
        # Verifica si ya existe esta evaluación para no duplicarla al correr el script de nuevo
        if Evaluaciones.objects.filter(
            proyecto=proyecto,
            fecha_evaluacion=fecha
        ).exists():
            continue

        # Guardamos usando el objeto evaluador que encontramos arriba
        Evaluaciones.objects.create(
            proyecto=proyecto,
            evaluador=evaluador_obj,  
            tipo_revision=tipo_revision,
            resolutivo="PENDIENTE",
            observaciones=observaciones,
            fecha_evaluacion=fecha
        )

        count += 1

    return count, errores