# evaluations/models.py

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Max
from django.db.models.signals import post_delete
from django.dispatch import receiver
from projects.models import Proyecto
from people.models import Evaluador


RESOLUTIVOS_QUE_CONSUMEN_INTENTO = ("APROBADO", "PENDIENTE", "RECHAZADO")


def recalcular_dictamen(proyecto_id):
    evaluaciones = Evaluaciones.objects.filter(proyecto_id=proyecto_id)

    tiene_aprobacion_final = evaluaciones.filter(
        tipo_revision="FINAL",
        resolutivo="APROBADO",
    ).exists()
    intentos_resueltos = evaluaciones.filter(
        resolutivo__in=RESOLUTIVOS_QUE_CONSUMEN_INTENTO,
    ).count()

    if tiene_aprobacion_final:
        dictamen = "APROBADO"
    elif intentos_resueltos >= 3:
        dictamen = "NO APROBADO"
    else:
        dictamen = "PENDIENTE"

    Proyecto.objects.filter(pk=proyecto_id).update(dictamen=dictamen)


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
        constraints = [
            models.UniqueConstraint(
                fields=("proyecto", "no_revision"),
                name="evaluacion_proyecto_no_revision_unica",
            ),
        ]

    def save(self, *args, **kwargs):
        es_nueva = self.pk is None

        with transaction.atomic():
            proyecto = self.proyecto
            if es_nueva:
                proyecto = proyecto.__class__.objects.select_for_update().get(
                    pk=self.proyecto_id
                )
            else:
                proyecto = proyecto.__class__.objects.select_for_update().get(
                    pk=self.proyecto_id
                )

            intentos_previos = Evaluaciones.objects.filter(
                proyecto_id=self.proyecto_id,
                resolutivo__in=RESOLUTIVOS_QUE_CONSUMEN_INTENTO,
            ).exclude(pk=self.pk).count()
            consume_intento = self.resolutivo in RESOLUTIVOS_QUE_CONSUMEN_INTENTO

            if consume_intento and intentos_previos >= 3:
                raise ValidationError(
                    "El proyecto ya alcanzó el límite de tres evaluaciones resueltas."
                )

            if es_nueva:
                ultimo_numero = Evaluaciones.objects.filter(
                    proyecto_id=self.proyecto_id,
                ).aggregate(maximo=Max("no_revision"))["maximo"] or 0
                self.no_revision = ultimo_numero + 1

            for field in self._meta.fields:
                if isinstance(field, (models.CharField, models.TextField)):
                    valor = getattr(self, field.name)
                    if isinstance(valor, str):
                        setattr(self, field.name, valor.upper())

            super().save(*args, **kwargs)
            recalcular_dictamen(self.proyecto_id)

    def delete(self, *args, **kwargs):
        proyecto_id = self.proyecto_id
        with transaction.atomic():
            resultado = super().delete(*args, **kwargs)
            recalcular_dictamen(proyecto_id)
        return resultado


@receiver(post_delete, sender=Evaluaciones)
def recalcular_dictamen_despues_de_eliminar(sender, instance, **kwargs):
    recalcular_dictamen(instance.proyecto_id)