from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from people.models import Evaluador
from projects.models import Proyecto

from .models import Evaluaciones


class EvaluacionesModelTests(TestCase):
	def setUp(self):
		self.proyecto = Proyecto.objects.create(
			folio="TEST-001",
			titulo="Proyecto de prueba",
			modalidad="PROTOTIPO",
			calendario_registro="2026B",
		)
		self.evaluador = Evaluador.objects.create(
			codigo_evaluador="EV-001",
			nombre_completo="Evaluador de prueba",
			correo_evaluador="evaluador@example.com",
			especializacion="General",
		)

	def crear_evaluacion(self, resolutivo="NO_APLICA", tipo_revision="FORMA"):
		return Evaluaciones.objects.create(
			proyecto=self.proyecto,
			evaluador=self.evaluador,
			fecha_evaluacion=timezone.now(),
			tipo_revision=tipo_revision,
			resolutivo=resolutivo,
		)

	def test_no_aplica_no_consumes_intento(self):
		for _ in range(3):
			self.crear_evaluacion()

		for _ in range(3):
			self.crear_evaluacion(resolutivo="PENDIENTE")

		with self.assertRaises(ValidationError):
			self.crear_evaluacion(resolutivo="RECHAZADO")

		self.proyecto.refresh_from_db()
		self.assertEqual(self.proyecto.dictamen, "NO APROBADO")

	def test_solo_aprobacion_final_cierra_el_proyecto(self):
		self.crear_evaluacion(resolutivo="APROBADO")

		self.proyecto.refresh_from_db()
		self.assertEqual(self.proyecto.dictamen, "PENDIENTE")

		self.crear_evaluacion(
			resolutivo="APROBADO",
			tipo_revision="FINAL",
		)

		self.proyecto.refresh_from_db()
		self.assertEqual(self.proyecto.dictamen, "APROBADO")

	def test_editar_evaluacion_recalcula_dictamen(self):
		evaluacion = self.crear_evaluacion(
			resolutivo="APROBADO",
			tipo_revision="FINAL",
		)
		evaluacion.resolutivo = "PENDIENTE"
		evaluacion.save()

		self.proyecto.refresh_from_db()
		self.assertEqual(self.proyecto.dictamen, "PENDIENTE")

	def test_eliminar_evaluacion_recalcula_dictamen(self):
		evaluaciones = [
			self.crear_evaluacion(resolutivo="RECHAZADO")
			for _ in range(3)
		]
		self.proyecto.refresh_from_db()
		self.assertEqual(self.proyecto.dictamen, "NO APROBADO")

		evaluaciones[0].delete()

		self.proyecto.refresh_from_db()
		self.assertEqual(self.proyecto.dictamen, "PENDIENTE")

	def test_numero_de_revision_se_asigna_por_proyecto(self):
		primera = self.crear_evaluacion()
		segunda = self.crear_evaluacion()

		self.assertEqual(primera.no_revision, 1)
		self.assertEqual(segunda.no_revision, 2)
