# evaluations/models.py

from django.db import models
from projects.models import Proyecto
from people.models import Evaluador


class Evaluaciones(models.Model):

    id_evaluacion = models.AutoField(primary_key=True, verbose_name="ID DE EVALUACIÓN")

    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        verbose_name="PROYECTO EVALUADO"
    )

    evaluador = models.ForeignKey(
        Evaluador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="EVALUADOR ASIGNADO"
    )

    fecha_evaluacion = models.DateTimeField(verbose_name="FECHA DE EVALUACIÓN")

    no_revision = models.PositiveIntegerField(
        default=1, 
        verbose_name="NÚMERO DE REVISIÓN"
    )
    
    REVISION_CHOICES = [
        ('FORMA', 'Revisión de Forma'),
        ('FONDO', 'Revisión de Fondo'),
        ('FINAL', 'Dictamen Final'),
    ]

    tipo_revision = models.CharField(
        max_length=10,
        choices=REVISION_CHOICES,
        default='FORMA',
        verbose_name="TIPO DE REVISIÓN"
    )

    RESOLUTIVO_CHOICES = [
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
        ('PENDIENTE', 'Pendiente de Correcciones'),
        ('NO_APLICA', 'No Aplica'),
    ]

    resolutivo = models.CharField(
        max_length=20,
        choices=RESOLUTIVO_CHOICES,
        default="NO_APLICA",
        verbose_name="RESOLUTIVO DE LA REVISIÓN"
    )

    observaciones = models.TextField(blank=True, null=True, verbose_name="OBSERVACIONES DETALLADAS")

    class Meta:
        verbose_name = "Evaluación Histórica"
        verbose_name_plural = "Evaluaciones Históricas"
        ordering = ['-fecha_evaluacion']

    def save(self, *args, **kwargs):
        if not self.pk: 
            # Contamos cuántas evaluaciones tiene YA este proyecto
            conteo_previo = Evaluaciones.objects.filter(proyecto=self.proyecto).count()
            # La nueva revisión será el conteo + 1
            self.no_revision = conteo_previo + 1

        # Convertir textos a MAYÚSCULAS
        for field in self._meta.fields:
            if isinstance(field, (models.CharField, models.TextField)):
                valor = getattr(self, field.name)
                if isinstance(valor, str):
                    setattr(self, field.name, valor.upper())

        super().save(*args, **kwargs)
