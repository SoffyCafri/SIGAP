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
RANGE_NAME = "Respuestas de formulario 1!A:Z"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


# ============================
# UTILIDADES
# ============================

def normalizar(texto):
    if not texto:
        return ""
    return texto.strip().upper()


def codigo_valido(codigo):
    return bool(re.fullmatch(r"\d{9}", str(codigo)))


def obtener_calendario(fecha):
    return "A" if fecha.month <= 6 else "B"


# ============================
# COMMAND
# ============================

class Command(BaseCommand):
    help = "Importa respuestas de Google Forms a SIGAP"

    def handle(self, *args, **options):
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

        if not rows:
            self.stdout.write(self.style.WARNING("No hay datos en el Sheet"))
            return

        headers = [h.strip() for h in rows[0]]
        data_rows = rows[1:]

        for row in data_rows:
            data = dict(zip(headers, row))
            self.procesar_registro(data)

        self.stdout.write(self.style.SUCCESS("✔ Importación finalizada"))


    # ============================
    # PROCESAMIENTO PRINCIPAL
    # ============================

    def procesar_registro(self, data):
        # ----------------------------
        # FECHA Y CALENDARIO
        # ----------------------------
        try:
            fecha = make_aware(datetime.strptime(
                data["Marca temporal"], "%d/%m/%Y %H:%M:%S"
            ))
        except Exception:
            return

        calendario = obtener_calendario(fecha)
        anio = fecha.year


        # ----------------------------
        # ALUMNOS
        # ----------------------------
        alumnos = []

        integrantes = [
            (
                data.get("Nombre de integrante 1(representante)"),
                data.get("Codigo de integrante 1(representante)"),
                data.get("Dirección de correo electrónico"),
                True
            ),
            (
                data.get("Nombre de integrante 2"),
                data.get("Codigo de integrante 2"),
                None,
                False
            ),
            (
                data.get("Nombre de integrante 3"),
                data.get("Codigo de integrante 3"),
                None,
                False
            )
        ]

        for nombre, codigo, correo, es_rep in integrantes:
            if not nombre or not codigo:
                if es_rep:
                    return  # representante obligatorio
                continue

            if not codigo_valido(codigo):
                return  # descarta todo el registro

            alumno, _ = Alumno.objects.get_or_create(
                codigo_estudiante=codigo,
                defaults={
                    "nombre_completo": normalizar(nombre),
                    "correo_electronico": correo if es_rep else None
                }
            )

            alumnos.append((alumno, es_rep))

        if not alumnos:
            return

        representante = next(a for a, r in alumnos if r)


        # ----------------------------
        # ASESOR
        # ----------------------------
        asesor, _ = Asesor.objects.get_or_create(
            codigo_asesor=data.get("Codigo del asesor"),
            defaults={
                "nombre_completo": normalizar(data.get("Nombre del asesor")),
                "correo_electronico": data.get("Correo institucional del asesor(a)")
            }
        )


        # ----------------------------
        # VARIANTE (solo la que tenga valor)
        # ----------------------------
        variante = next(
            (normalizar(v) for k, v in data.items() if k.strip().upper() == "VARIANTE" and v),
            None
        )


        # ----------------------------
        # EVIDENCIA (solo la que tenga valor)
        # ----------------------------
        evidencia = next(
            (v for k, v in data.items() if k.strip().upper() == "EVIDENCIA" and v),
            None
        )


        # ----------------------------
        # PROYECTO
        # ----------------------------
        folio = f"{representante.codigo_estudiante}-{anio}{calendario}"

        proyecto, _ = Proyecto.objects.get_or_create(
            folio=folio,
            defaults={
                "titulo": normalizar(data.get("Titulo del proyecto")),
                "asesor": asesor,
                "modalidad": normalizar(data.get("Modalidad")),
                "variante": variante,
                "nivel_competencia": normalizar(data.get("Nivel de competencias")),
                "calendario_registro": f"{anio}{calendario}",
                "evidencia_url": data.get("SUBE TU EVIDENCIA") or evidencia,
                "protocolo_dictamen_url": data.get("SUBE TU FORMATO")
            }
        )


        # ----------------------------
        # FORMATO 1 (1:1)
        # ----------------------------
        intro = normalizar(data.get("INTRODUCCION"))
        just = normalizar(data.get("JUSTIFICACION"))
        obj = normalizar(data.get("OBJETIVO"))
        res = normalizar(data.get("RESUMEN"))

        if any([intro, just, obj, res]):
            Formato1.objects.get_or_create(
                folio=folio,
                defaults={
                    "introduccion": intro,
                    "justificacion": just,
                    "objetivo": obj,
                    "resumen": res
                }
            )


        # ----------------------------
        # PARTICIPACIONES (M:M)
        # ----------------------------
        for alumno, es_rep in alumnos:
            Participacion.objects.get_or_create(
                proyecto=proyecto,
                alumno=alumno,
                defaults={"es_representante": es_rep}
            )

        self.stdout.write(f"✔ Proyecto importado: {folio}")
