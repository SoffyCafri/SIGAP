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
        # 1. LÓGICA DE MAYÚSCULAS Y CONTEO (Lo que ya tenías)
        is_new = self.pk is None # Detectamos si es nuevo antes de guardar
        
        if is_new:
            # Contamos cuántas hay guardadas en BD (sin contar esta nueva aún)
            conteo_previo = Evaluaciones.objects.filter(proyecto=self.proyecto).count()
            self.no_revision = conteo_previo + 1

        for field in self._meta.fields:
            if isinstance(field, (models.CharField, models.TextField)):
                valor = getattr(self, field.name)
                if isinstance(valor, str):
                    setattr(self, field.name, valor.upper())

        # 2. GUARDAMOS LA EVALUACIÓN PRIMERO
        # Es necesario guardar primero para que el registro exista y sea oficial
        super().save(*args, **kwargs)

        # 3. LÓGICA DE ACTUALIZACIÓN DEL PROYECTO
        proyecto = self.proyecto
        hubo_cambios = False # Bandera para saber si necesitamos guardar el proyecto

        # Obtenemos el conteo total ACTUALIZADO (incluyendo la que acabamos de guardar)
        total_evaluaciones = Evaluaciones.objects.filter(proyecto=proyecto).count()

        # --- CASO A: APROBADO ---
        # Si esta evaluación es APROBADO, el proyecto se aprueba (sin importar el intento)
        if self.resolutivo == 'APROBADO':
            if proyecto.dictamen != 'APROBADO': # Solo si cambia el estado
                proyecto.dictamen = 'APROBADO'
                hubo_cambios = True

        # --- CASO B: GAME OVER (3 INTENTOS FALLIDOS) ---
        # Si llevamos 3 o más intentos y este último NO es aprobado...
        elif total_evaluaciones >= 3 and self.resolutivo != 'APROBADO':
            if proyecto.dictamen != 'NO APROBADO': # Solo si cambia el estado
                proyecto.dictamen = 'NO APROBADO'
                hubo_cambios = True

        # 4. GUARDAR CAMBIOS EN EL PROYECTO (Solo si es necesario)
        if hubo_cambios:
            proyecto.save()
