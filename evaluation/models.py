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
        # 1. LÓGICA DE MAYÚSCULAS Y CONTEO
        is_new = self.pk is None 
        
        if is_new:
            conteo_previo = Evaluaciones.objects.filter(proyecto=self.proyecto).count()
            self.no_revision = conteo_previo + 1

        for field in self._meta.fields:
            if isinstance(field, (models.CharField, models.TextField)):
                valor = getattr(self, field.name)
                if isinstance(valor, str):
                    setattr(self, field.name, valor.upper())

        # 2. GUARDAR EVALUACIÓN
        super().save(*args, **kwargs)

        # 3. LÓGICA DE ACTUALIZACIÓN DEL PROYECTO
        # FILTRO DE SEGURIDAD:
        # Si la evaluación sigue en "NO_APLICA", ignoramos todo. 
        # No aprobamos ni reprobamos el proyecto todavía.
        if self.resolutivo == "NO_APLICA":
            return  

        proyecto = self.proyecto
        hubo_cambios = False 

        total_evaluaciones = Evaluaciones.objects.filter(proyecto=proyecto).count()

        # --- CASO A: APROBADO ---
        if self.resolutivo == 'APROBADO':
            if proyecto.dictamen != 'APROBADO':
                proyecto.dictamen = 'APROBADO'
                hubo_cambios = True

        # --- CASO B: GAME OVER (3 INTENTOS FALLIDOS) ---
        # Como ya filtramos el "NO_APLICA" arriba, aquí solo entra PENDIENTE o RECHAZADO
        elif total_evaluaciones >= 3 and self.resolutivo != 'APROBADO':
            if proyecto.dictamen != 'NO APROBADO': 
                proyecto.dictamen = 'NO APROBADO'
                hubo_cambios = True

        if hubo_cambios:
            proyecto.save()