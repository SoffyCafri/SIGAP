from django.contrib import admin, messages
from django.core.mail import send_mail
from django.conf import settings
from django.urls import path
from django.shortcuts import redirect
from django.utils import timezone

from .models import Evaluaciones
from .import_evaluaciones_forms import importar_evaluaciones_forms
from django.utils.html import format_html
from django.utils.safestring import mark_safe


admin.site.site_header = "Panel Administrativo QFB"
admin.site.site_title = "QFB | Administración"
admin.site.index_title = "Gestión de Proyectos Modulares"
admin.site.site_url = None


@admin.register(Evaluaciones)
class EvaluacionesAdmin(admin.ModelAdmin):
    list_display = ('no_revision', 'proyecto', 'evaluador', 'tipo_revision', 'resolutivo', 'fecha_evaluacion')
    list_editable = ('resolutivo',)
    list_filter = ('tipo_revision', 'resolutivo', 'evaluador', 'fecha_evaluacion')
    search_fields = ('proyecto__folio', 'evaluador__nombre_completo', 'observaciones')

    readonly_fields = ('no_revision',)
    autocomplete_fields = ['proyecto', 'evaluador']

    change_list_template = "admin/projects/proyecto/evaluaciones_change_list.html"

    # DEFAULT EN ADMIN
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj is None:
            form.base_fields["resolutivo"].initial = "NO_APLICA"
            form.base_fields["fecha_evaluacion"].initial = timezone.now()
        return form

    # 🔥 ENVÍO DE CORREO CUANDO SE APRUEBA
    def save_model(self, request, obj, form, change):
        resolutivo_anterior = None

        if change:
            resolutivo_anterior = Evaluaciones.objects.get(pk=obj.pk).resolutivo

        super().save_model(request, obj, form, change)

        if obj.resolutivo == "APROBADO" and resolutivo_anterior != "APROBADO":
            rep = obj.proyecto.participacion_set.filter(es_representante=True).first()

            if rep and rep.alumno.correo_electronico:
                send_mail(
                    subject="🎉 Tu proyecto fue APROBADO",
                    message=f"Tu proyecto con folio {obj.proyecto.folio} fue APROBADO por tu evaluador.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[rep.alumno.correo_electronico],
                    fail_silently=False,
                )

    # ✅ BOTÓN IMPORTAR
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "importar-evaluaciones-forms/",
                self.admin_site.admin_view(self.importar_evaluaciones_forms_view),
                name="importar_evaluaciones_forms"
            )
        ]
        return custom_urls + urls

    def importar_evaluaciones_forms_view(self, request):
        try:
            # 1. Desempaquetamos los DOS valores de retorno
            total_exitos, lista_errores = importar_evaluaciones_forms()
            
            # 2. Mensaje de Éxito 
            if total_exitos > 0:
                messages.success(request, f"✔ Éxito: Se crearon {total_exitos} evaluaciones nuevas.")
            
            # 3. Mensaje de Advertencia con Detalles 
            if lista_errores:
                # Convertimos la lista de errores en una lista HTML
                items_html = "".join([f"<li>{err}</li>" for err in lista_errores])
                mensaje_html = format_html(
                    "⚠ Se encontraron los siguientes problemas en el archivo:<br>"
                    "<ul style='margin-top:5px; margin-bottom:0;'>{}</ul>",
                    mark_safe(items_html)
                )
                # Usamos el nivel WARNING para que salga amarillo
                messages.warning(request, mensaje_html)

            # 4. Mensaje Informativo 
            if total_exitos == 0 and not lista_errores:
                messages.info(request, "ℹ El proceso terminó correctamente, pero no había registros nuevos para importar.")

        except FileNotFoundError as e:
            messages.error(request, str(e))
            
        except Exception as e:
            messages.error(request, f"❌ Ocurrió un error inesperado: {e}")

        return redirect("..")
