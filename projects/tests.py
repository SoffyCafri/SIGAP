from itertools import product

from django.test import SimpleTestCase

from .fuzzy_priority import calcular_prioridad_proyecto


class FuzzyPriorityTests(SimpleTestCase):
    def test_all_27_combinations_have_a_result(self):
        for dias, documentos, revisiones in product(
            (0, 15, 30),
            (0, 1.5, 3),
            (0, 1.5, 3),
        ):
            puntaje, etiqueta = calcular_prioridad_proyecto(
                dias, documentos, revisiones
            )
            self.assertGreaterEqual(puntaje, 0)
            self.assertLessEqual(puntaje, 100)
            self.assertIn(etiqueta, {"BAJA", "MEDIA", "ALTA", "URGENTE"})

    def test_more_elapsed_days_increases_priority(self):
        prioridad_reciente, _ = calcular_prioridad_proyecto(0, 1, 1)
        prioridad_rezagada, _ = calcular_prioridad_proyecto(30, 1, 1)

        self.assertGreater(prioridad_rezagada, prioridad_reciente)

    def test_approved_resolution_reduces_priority(self):
        prioridad_pendiente, _ = calcular_prioridad_proyecto(5, 2, 2)
        prioridad_aprobada, etiqueta_aprobada = calcular_prioridad_proyecto(
            5, 2, 2, aprobado=True
        )

        self.assertLess(prioridad_aprobada, prioridad_pendiente)
        self.assertEqual(etiqueta_aprobada, "ALTA")
