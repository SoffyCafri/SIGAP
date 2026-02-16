from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from django.conf import settings
from projects.models import Proyecto, Formato1 # Importamos ambos modelos
import os

# ================= CONFIGURACIÓN =================
SPREADSHEET_ID = "1hQseBivdPwLe9roXOxjmRbscUNriAvj5Fydih8jSHKs" 
# Usamos A:Z para asegurar que lea todas las columnas aunque agregues más
RANGE_NAME = "'Respuestas de formulario 1'!A:Z" 
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
RUTA_CREDENCIALES = os.path.join(settings.BASE_DIR, "google_service_account.json.json")

def normalizar(texto):
    return texto.strip().upper() if texto else ""

def importar_correcciones_formato1():
    print("--- INICIANDO IMPORTACIÓN DE CORRECCIONES ---")

    if not os.path.exists(RUTA_CREDENCIALES):
        raise FileNotFoundError(f"❌ No se encontró el archivo de credenciales.")
    
    try:
        creds = Credentials.from_service_account_file(RUTA_CREDENCIALES, scopes=SCOPES)
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
    except Exception as e:
        raise Exception(f"Error conectando con Google Sheets: {e}")

    rows = result.get("values", [])
    if not rows:
        return 0, []

    # Normalizamos headers a MAYÚSCULAS para evitar errores de case-sensitive
    headers = [h.strip().upper() for h in rows[0]]
    print(f"HEADERS DETECTADOS: {headers}") # Para debug

    data_rows = rows[1:]
    count = 0
    errores = []

    # ==============================================================================
    # 🎯 MAPEO EXACTO BASADO EN TU CAPTURA DE PANTALLA
    # ==============================================================================
    # 1. Nombre exacto de la columna del folio (en mayúsculas)
    COLUMNA_FOLIO = "INGRESA TU FOLIO DE PROYECTO ASIGNADO"

    # 2. Diccionario: "COLUMNA EXCEL" : "campo_en_modelo_django"
    # Asegúrate que los campos de la derecha existan en tu modelo Formato1
    MAPEO_CAMPOS = {
        "INTRODUCCIÓN": "introduccion",       # Ojo con el acento en el Excel
        "JUSTIFICACIÓN": "justificacion",     # Ojo con el acento en el Excel
        "OBJETIVO": "objetivo",               # En tu foto está en SINGULAR
        "RESUMEN": "resumen"
    }

    for i, row in enumerate(data_rows):
        num_fila = i + 2
        
        # Rellenar columnas faltantes
        if len(row) < len(headers):
            row += [None] * (len(headers) - len(row))
        
        data = dict(zip(headers, row))

        # --- A. OBTENER FOLIO ---
        folio = data.get(COLUMNA_FOLIO)
        
        if not folio:
            # Si la fila está vacía o no tiene folio, la saltamos sin error
            continue 

        # --- B. BUSCAR EL PROYECTO ---
        try:
            proyecto = Proyecto.objects.get(folio=folio.strip())
        except Proyecto.DoesNotExist:
            errores.append(f"Fila {num_fila}: Folio '{folio}' NO existe en la base de datos.")
            continue

        # --- C. VALIDAR ESTADO (Candado) ---
        if proyecto.dictamen in ['APROBADO', 'NO APROBADO']:
            errores.append(f"Fila {num_fila}: PROYECTO CERRADO ({folio}). Estado: {proyecto.dictamen}.")
            continue

        # --- D. OBTENER EL FORMATO 1 ASOCIADO ---
        # No guardamos en 'Proyecto', guardamos en 'Formato1'
        # Usamos el related_name 'formato1_data' que definimos antes
        if hasattr(proyecto, 'formato1_data'):
            formato = proyecto.formato1_data
        else:
            # Si el proyecto existe pero no tiene Formato 1 creado, intentamos crearlo o reportamos error
            # Aquí reportaremos error para que se sepa que falta data inicial
            errores.append(f"Fila {num_fila}: El proyecto {folio} existe pero NO tiene un Formato 1 inicial registrado.")
            continue

        # --- E. ACTUALIZAR CAMPOS ---
        cambios_realizados = False
        
        for header_excel, campo_modelo in MAPEO_CAMPOS.items():
            valor_nuevo = data.get(header_excel)
            
            # Pro Tip: Usar .strip() y convertir a string para evitar problemas con None
            val_db = str(getattr(formato, campo_modelo, "") or "").strip()
            val_excel = str(valor_nuevo).strip()

            if val_db != val_excel:
                setattr(formato, campo_modelo, valor_nuevo) # Guardamos el valor original del Excel
                cambios_realizados = True
        
        if cambios_realizados:
            formato.save()
            count += 1
        # No marcamos error si no hubo cambios, significa que el alumno subió lo mismo

    return count, errores