import numpy as np
import skfuzzy as fuzz
from skfuzzy.defuzzify.exceptions import EmptyMembershipError


def calcular_prioridad_proyecto(
    dias_fecha_limite, documentos_pendientes, revisiones_realizadas
):
    """Calcula la prioridad de un proyecto mediante un Sistema de Inferencia Difusa Mamdani.

    Entradas:
      - dias_fecha_limite: rango 0 a 30 días
      - documentos_pendientes: rango 0 a 2 documentos
      - revisiones_realizadas: rango 0 a 3 revisiones

    Retorna:
      (prioridad, etiqueta) donde prioridad está en [0,100] y etiqueta es una de:
      'BAJA', 'MEDIA', 'ALTA', 'URGENTE'
    """
    dias = float(np.clip(dias_fecha_limite, 0, 30))
    documentos = float(np.clip(documentos_pendientes, 0, 2))
    revisiones = float(np.clip(revisiones_realizadas, 0, 3))

    universo_dias = np.linspace(0, 30, 301)
    universo_documentos = np.linspace(0, 2, 201)
    universo_revisiones = np.linspace(0, 3, 301)
    universo_prioridad = np.linspace(0, 100, 1001)

    dias_critico = fuzz.trapmf(universo_dias, [0, 0, 5, 10])
    dias_medio = fuzz.trimf(universo_dias, [5, 15, 25])
    dias_urgente = fuzz.trapmf(universo_dias, [20, 25, 30, 30])

    docs_ninguno = fuzz.trapmf(universo_documentos, [0, 0, 0.5, 1])
    docs_pocos = fuzz.trimf(universo_documentos, [0.5, 1, 1.5])
    docs_muchos = fuzz.trapmf(universo_documentos, [1, 1.5, 2, 2])

    revis_ninguna = fuzz.trapmf(universo_revisiones, [0, 0, 0.5, 1])
    revis_pocas = fuzz.trimf(universo_revisiones, [0.5, 1.5, 2.5])
    revis_muchas = fuzz.trapmf(universo_revisiones, [2, 2.5, 3, 3])

    prioridad_baja = fuzz.trapmf(universo_prioridad, [0, 0, 20, 35])
    prioridad_media = fuzz.trimf(universo_prioridad, [20, 50, 80])
    prioridad_alta = fuzz.trimf(universo_prioridad, [50, 70, 90])
    prioridad_urgente = fuzz.trapmf(universo_prioridad, [70, 85, 100, 100])

    dias_critico_val = fuzz.interp_membership(
        universo_dias, dias_critico, dias
    )
    dias_medio_val = fuzz.interp_membership(universo_dias, dias_medio, dias)
    dias_urgente_val = fuzz.interp_membership(
        universo_dias, dias_urgente, dias
    )

    docs_ninguno_val = fuzz.interp_membership(
        universo_documentos, docs_ninguno, documentos
    )
    docs_pocos_val = fuzz.interp_membership(
        universo_documentos, docs_pocos, documentos
    )
    docs_muchos_val = fuzz.interp_membership(
        universo_documentos, docs_muchos, documentos
    )

    revis_ninguna_val = fuzz.interp_membership(
        universo_revisiones, revis_ninguna, revisiones
    )
    revis_pocas_val = fuzz.interp_membership(
        universo_revisiones, revis_pocas, revisiones
    )
    revis_muchas_val = fuzz.interp_membership(
        universo_revisiones, revis_muchas, revisiones
    )

    reg1 = np.fmin(
        np.fmin(dias_critico_val, docs_ninguno_val), revis_ninguna_val
    )
    reg2 = np.fmin(np.fmin(dias_critico_val, docs_pocos_val), revis_pocas_val)
    reg3 = np.fmin(np.fmin(dias_medio_val, docs_pocos_val), revis_pocas_val)
    reg4 = np.fmin(np.fmin(dias_urgente_val, docs_muchos_val), revis_muchas_val)
    reg5 = np.fmin(np.fmin(dias_urgente_val, docs_pocos_val), revis_muchas_val)
    reg6 = np.fmin(np.fmin(dias_medio_val, docs_muchos_val), revis_pocas_val)

    cons1 = np.fmin(reg1, prioridad_baja)
    cons2 = np.fmin(reg2, prioridad_media)
    cons3 = np.fmin(reg3, prioridad_alta)
    cons4 = np.fmin(reg4, prioridad_urgente)
    cons5 = np.fmin(reg5, prioridad_urgente)
    cons6 = np.fmin(reg6, prioridad_alta)

    agregado = np.zeros_like(universo_prioridad)
    for cons in (cons1, cons2, cons3, cons4, cons5, cons6):
        agregado = np.maximum(agregado, cons)

    if np.max(agregado) == 0:
        if dias_urgente_val > 0:
            puntaje = 85.0
        elif dias_critico_val > 0:
            puntaje = 65.0
        elif docs_muchos_val > 0 or revis_muchas_val > 0:
            puntaje = 55.0
        else:
            puntaje = 0.0
    else:
        try:
            puntaje = fuzz.defuzz(universo_prioridad, agregado, "centroid")
            puntaje = float(np.clip(puntaje, 0, 100))
        except EmptyMembershipError:
            puntaje = 0.0

    # Clasificación de etiqueta
    if puntaje < 25:
        etiqueta = "BAJA"
    elif puntaje < 50:
        etiqueta = "MEDIA"
    elif puntaje < 75:
        etiqueta = "ALTA"
    else:
        etiqueta = "URGENTE"

    return round(puntaje, 2), etiqueta