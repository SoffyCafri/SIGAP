# evaluations/admin.py

from django.contrib import admin
from django.core.mail import send_mail
from django.conf import settings
from .models import Evaluaciones


admin.site.site_header = "Panel Administrativo QFB"
admin.site.site_title = "QFB | Administración"
admin.site.index_title = "Gestión de Proyectos Modulares"
admin.site.site_url = None


@admin.register(Evaluaciones)
class EvaluacionesAdmin(admin.ModelAdmin):
    list_display = ('id_evaluacion', 'proyecto', 'evaluador', 'tipo_revision', 'resolutivo', 'fecha_evaluacion')
    list_editable = ('resolutivo',)
    list_filter = ('tipo_revision', 'resolutivo', 'evaluador', 'fecha_evaluacion')
    search_fields = ('proyecto__folio', 'evaluador__nombre_completo', 'observaciones')

    readonly_fields = ('fecha_evaluacion',)
    autocomplete_fields = ['proyecto', 'evaluador']

    # DEFAULT EN ADMIN
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj is None:
            form.base_fields["resolutivo"].initial = "NO_APLICA"
        return form

    # 🔥 ENVÍO DE CORREO CUANDO SE APRUEBA
    def save_model(self, request, obj, form, change):
        resolutivo_anterior = None

        if change:
            resolutivo_anterior = Evaluaciones.objects.get(pk=obj.pk).resolutivo

        super().save_model(request, obj, form, change)

        # Solo enviar si cambió a APROBADO
        if obj.resolutivo == "APROBADO" and resolutivo_anterior != "APROBADO":

            rep = obj.proyecto.participacion_set.filter(es_representante=True).first()

            if rep and rep.alumno.correo_electronico:
                send_mail(
                    subject="🎉 Tu proyecto fue APROBADO",
                    message=f"Tu proyecto con folio {obj.proyecto.folio} fue APROBADO.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[rep.alumno.correo_electronico],
                    fail_silently=False,
                )
