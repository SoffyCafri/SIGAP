import numpy as np
import skfuzzy as fuzz
from skfuzzy.defuzzify.exceptions import EmptyMembershipError


def calcular_prioridad_proyecto(
    dias_transcurridos,
    documentos_pendientes,
    revisiones_realizadas,
    aprobado=False,
):
    """Calcula la prioridad mediante un sistema de inferencia difusa Mamdani.

    Entradas:
      - dias_transcurridos: días transcurridos desde el registro, limitado a 30
      - documentos_pendientes: rango 0 a 3 documentos
      - revisiones_realizadas: rango 0 a 3 revisiones
      - aprobado: si existe un resolutivo APROBADO, reduce un nivel la prioridad

    Retorna:
      (prioridad, etiqueta) donde prioridad está en [0,100] y etiqueta es una de:
      'BAJA', 'MEDIA', 'ALTA', 'URGENTE'
    """
    dias = float(np.clip(dias_transcurridos, 0, 30))
    documentos = float(np.clip(documentos_pendientes, 0, 3))
    revisiones = float(np.clip(revisiones_realizadas, 0, 3))

    universo_dias = np.linspace(0, 30, 301)
    universo_documentos = np.linspace(0, 3, 301)
    universo_revisiones = np.linspace(0, 3, 301)
    universo_prioridad = np.linspace(0, 100, 1001)

    dias_reciente = fuzz.trapmf(universo_dias, [0, 0, 5, 10])
    dias_medio = fuzz.trimf(universo_dias, [5, 15, 25])
    dias_rezagado = fuzz.trapmf(universo_dias, [20, 25, 30, 30])

    docs_ninguno = fuzz.trapmf(universo_documentos, [0, 0, 0.5, 1])
    docs_pocos = fuzz.trimf(universo_documentos, [0.5, 1.5, 2.5])
    docs_muchos = fuzz.trapmf(universo_documentos, [1.5, 2, 3, 3])

    revis_ninguna = fuzz.trapmf(universo_revisiones, [0, 0, 0.5, 1])
    revis_pocas = fuzz.trimf(universo_revisiones, [0.5, 1.5, 2.5])
    revis_muchas = fuzz.trapmf(universo_revisiones, [2, 2.5, 3, 3])

    prioridad_baja = fuzz.trapmf(universo_prioridad, [0, 0, 20, 35])
    prioridad_media = fuzz.trimf(universo_prioridad, [20, 50, 80])
    prioridad_alta = fuzz.trimf(universo_prioridad, [50, 70, 90])
    prioridad_urgente = fuzz.trapmf(universo_prioridad, [70, 85, 100, 100])

    dias_reciente_val = fuzz.interp_membership(universo_dias, dias_reciente, dias)
    dias_medio_val = fuzz.interp_membership(universo_dias, dias_medio, dias)
    dias_rezagado_val = fuzz.interp_membership(universo_dias, dias_rezagado, dias)

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

    grados_dias = (dias_reciente_val, dias_medio_val, dias_rezagado_val)
    grados_documentos = (docs_ninguno_val, docs_pocos_val, docs_muchos_val)
    grados_revisiones = (revis_ninguna_val, revis_pocas_val, revis_muchas_val)
    salidas = (prioridad_baja, prioridad_media, prioridad_alta, prioridad_urgente)

    # Las 27 combinaciones se generan desde una matriz completa de reglas.
    niveles = (
        (0, 0, 1),
        (1, 1, 2),
        (2, 2, 3),
    )
    if aprobado:
        niveles = tuple(
            tuple(max(nivel - 1, 0) for nivel in fila)
            for fila in niveles
        )

    consecuencias = []
    for indice_dias, grado_dias in enumerate(grados_dias):
        for indice_documentos, grado_documentos in enumerate(grados_documentos):
            for indice_revisiones, grado_revisiones in enumerate(grados_revisiones):
                regla = min(grado_dias, grado_documentos, grado_revisiones)
                nivel = min(
                    niveles[indice_dias][indice_documentos] + indice_revisiones,
                    3,
                )
                consecuencias.append(np.fmin(regla, salidas[nivel]))

    agregado = np.zeros_like(universo_prioridad)
    for cons in consecuencias:
        agregado = np.maximum(agregado, cons)

    if np.max(agregado) == 0:
        raise ValueError("Las funciones de pertenencia no cubren las entradas.")
    else:
        try:
            puntaje = fuzz.defuzz(universo_prioridad, agregado, "centroid")
            puntaje = float(np.clip(puntaje, 0, 100))
        except EmptyMembershipError:
            puntaje = 0.0

    if aprobado:
        puntaje = min(puntaje, 74.99)

    if puntaje < 25:
        etiqueta = "BAJA"
    elif puntaje < 50:
        etiqueta = "MEDIA"
    elif puntaje < 75:
        etiqueta = "ALTA"
    else:
        etiqueta = "URGENTE"

    return round(puntaje, 2), etiqueta