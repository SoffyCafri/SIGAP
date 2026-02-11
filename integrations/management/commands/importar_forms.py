from django.core.management.base import BaseCommand
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from django.utils.timezone import make_aware
from datetime import datetime
import re

from people.models import Alumno, Asesor
from projects.models import Proyecto, Formato1, Participacion

# ============================
# CONFIG GOOGLE SHEETS
# ============================

SPREADSHEET_ID = "17l-rBcNI95twCxpgWAS6ZW2-s9mNet_-MTG29eNxPfk"
RANGE_NAME = "Respuestas de formulario 1!A:ZZ"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# ============================
# UTILIDADES (Globales)
# ============================

def normalizar(texto):
    if not texto:
        return ""
    return texto.strip().upper()

def codigo_valido(codigo):
    return bool(re.fullmatch(r"\d{9}", str(codigo)))

def obtener_calendario(fecha):
    return "A" if fecha.month <= 6 else "B"

def buscar_valor_flexible(diccionario, palabra_clave):
    """
    Busca una columna que contenga la palabra clave en un diccionario ya procesado.
    """
    clave_limpia = palabra_clave.upper().strip()
    
    for key, value in diccionario.items():
        if not key: continue
        header_limpio = key.upper().strip()
        header_sin_acentos = header_limpio.replace('Ó', 'O').replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ú', 'U')
        
        if clave_limpia in header_sin_acentos:
            return value
    return None

def buscar_valor_repetido(headers, row, palabra_clave):
    """
    Busca en la lista cruda el PRIMER valor no vacío para columnas repetidas.
    """
    clave_limpia = palabra_clave.upper().strip()
    
    for h, valor in zip(headers, row):
        if not h or not valor: continue
        
        header_limpio = h.upper().strip()
        if clave_limpia in header_limpio:
            if str(valor).strip():
                return valor
    return None

# ============================
# COMMAND
# ============================

class Command(BaseCommand):
    help = "Importa respuestas de Google Forms a SIGAP"

    def handle(self, *args, **options):
        self.stdout.write("🔵 Iniciando conexión con Google Sheets...")
        
        RUTA_CREDENCIALES = "/app/SIGAP/credentials/google_service_account.json"
        
        try:
            creds = Credentials.from_service_account_file(RUTA_CREDENCIALES, scopes=SCOPES)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"❌ No se encontró el archivo de credenciales en: {RUTA_CREDENCIALES}"))
            return

        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()

        try:
            result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error al conectar con Google Sheets: {e}"))
            return

        rows = result.get("values", [])
        if not rows:
            self.stdout.write(self.style.WARNING("⚠ No hay datos en el Sheet"))
            return

        headers = [h.strip() for h in rows[0]]
        self.stdout.write(f"📋 Headers detectados: {len(headers)} columnas")

        data_rows = rows[1:]
        count = 0
        
        self.stdout.write(f"🔄 Procesando {len(data_rows)} filas...")

        for i, row in enumerate(data_rows):
            if len(row) < len(headers):
                row += [None] * (len(headers) - len(row))
            
            # 1. Detección de columnas repetidas (SOLO VARIANTES)
            # Ya no buscamos EVIDENCIA aquí para evitar la confusión con el texto
            variante_detectada = buscar_valor_repetido(headers, row, "VARIANTE")
            
            # 2. Diccionario estándar
            data = dict(zip(headers, row))
            
            if self.procesar_registro(data, i+1, variante_detectada):
                count += 1

        self.stdout.write(self.style.SUCCESS(f"✔ Importación finalizada. {count} proyectos procesados."))

    # ============================
    # PROCESAMIENTO
    # ============================

    def procesar_registro(self, data, num_fila, variante_raw):
        # 1. FECHA
        try:
            fecha_str = data.get("Marca temporal")
            if not fecha_str: return False
            fecha = make_aware(datetime.strptime(fecha_str, "%d/%m/%Y %H:%M:%S"))
        except Exception as e:
            print(f"❌ Fila {num_fila}: Error en fecha - {e}")
            return False

        calendario = obtener_calendario(fecha)
        anio = fecha.year

        # 2. ALUMNOS
        alumnos = []
        integrantes = [
            (data.get("Nombre de integrante 1(representante)"), data.get("Codigo de integrante 1(representante)"), data.get("Dirección de correo electrónico"), True),
            (data.get("Nombre de integrante 2"), data.get("Codigo de integrante 2"), None, False),
            (data.get("Nombre de integrante 3"), data.get("Codigo de integrante 3"), None, False)
        ]

        for nombre, codigo, correo, es_rep in integrantes:
            if not nombre or not codigo:
                if es_rep: return False 
                continue
            if not codigo_valido(codigo): return False

            alumno, _ = Alumno.objects.get_or_create(
                codigo_estudiante=codigo,
                defaults={
                    "nombre_completo": normalizar(nombre),
                    "correo_electronico": correo if es_rep else None
                }
            )
            if es_rep and correo and alumno.correo_electronico != correo:
                alumno.correo_electronico = correo
                alumno.save()
            alumnos.append((alumno, es_rep))

        if not alumnos: return False
        
        try:
            representante = next(a for a, r in alumnos if r)
        except StopIteration:
            return False

        # 3. ASESOR
        asesor = None
        codigo_asesor = data.get("Codigo del asesor")
        if codigo_asesor:
            asesor, _ = Asesor.objects.get_or_create(
                codigo_asesor=codigo_asesor,
                defaults={
                    "nombre_completo": normalizar(data.get("Nombre del asesor")),
                    "correo_electronico": data.get("Correo institucional del asesor(a)")
                }
            )

        # 4. PROYECTO
        folio = f"{representante.codigo_estudiante}-{anio}{calendario}"
        
        # --- CORRECCIÓN DE URLs ---
        # Buscamos específicamente las columnas de subida de archivos
        # Usamos buscar_valor_flexible para asegurar que encuentre "SUBE TU EVIDENCIA " (con espacios)
        url_evidencia = buscar_valor_flexible(data, "SUBE TU EVIDENCIA")
        url_protocolo = buscar_valor_flexible(data, "SUBE TU FORMATO")

        proyecto, created = Proyecto.objects.update_or_create(
            folio=folio,
            defaults={
                "titulo": normalizar(data.get("Titulo del proyecto")),
                "asesor": asesor,
                "modalidad": normalizar(data.get("Modalidad")),
                "variante": normalizar(variante_raw), 
                "nivel_competencia": normalizar(data.get("Nivel de competencias")),
                "calendario_registro": f"{anio}{calendario}",
                # Asignamos las variables correctas
                "evidencia_url": url_evidencia, 
                "protocolo_dictamen_url": url_protocolo
            }
        )

        # 5. FORMATO 1
        intro = normalizar(buscar_valor_flexible(data, "INTRODUCCION"))
        just = normalizar(buscar_valor_flexible(data, "JUSTIFICACION"))
        obj = normalizar(buscar_valor_flexible(data, "OBJETIVO"))
        res = normalizar(buscar_valor_flexible(data, "RESUMEN"))

        if any([intro, just, obj, res]):
            try:
                Formato1.objects.update_or_create(
                    proyecto=proyecto, 
                    defaults={
                        "introduccion": intro,
                        "justificacion": just,
                        "objetivo": obj,
                        "resumen": res
                    }
                )
            except Exception as e:
                print(f"❌ Error al guardar Formato1 para {folio}: {e}")
        
        # 6. PARTICIPACIONES
        for alumno_obj, es_rep in alumnos:
            Participacion.objects.get_or_create(
                proyecto=proyecto,
                alumno=alumno_obj,
                defaults={"es_representante": es_rep}
            )
            
        return True