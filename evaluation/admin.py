from django.contrib import admin, messages
from django.core.mail import send_mail, get_connection, EmailMessage # Importamos get_connection y EmailMessage
from django.conf import settings
from django.urls import path
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import Evaluaciones
from .import_evaluaciones_forms import importar_evaluaciones_forms


admin.site.site_header = "Panel Administrativo QFB"
admin.site.site_title = "QFB | Administración"
admin.site.index_title = "Gestión de Proyectos Modulares"
admin.site.site_url = None


@admin.register(Evaluaciones)
class EvaluacionesAdmin(admin.ModelAdmin):
    list_display = ('no_revision', 'proyecto', 'evaluador', 'tipo_revision', 'resolutivo', 'fecha_evaluacion')
    list_editable = ('resolutivo',) # Ojo: Úsalo con cuidado en ediciones masivas
    list_filter = ('tipo_revision', 'resolutivo', 'evaluador', 'fecha_evaluacion')
    search_fields = ('proyecto__folio', 'evaluador__nombre_completo', 'observaciones')

    # REGISTRAMOS LAS 3 ACCIONES MASIVAS
    actions = ['accion_aprobar_masivo', 'accion_correcciones_masivo', 'accion_rechazar_masivo']

    readonly_fields = ('no_revision',)
    autocomplete_fields = ['proyecto', 'evaluador']

    change_list_template = "admin/projects/proyecto/evaluaciones_change_list.html"

    # =================================================================
    # MOTOR CENTRAL DE PROCESAMIENTO MASIVO (Reutilizable)
    # =================================================================
    def _procesar_cambio_masivo(self, request, queryset, nuevo_estado):
        """
        Función auxiliar que maneja la conexión eficiente y la lógica de correos
        para evitar duplicar código y timeouts.
        """
        # Filtramos para no reprocesar lo que ya tiene ese estado (Evita Spam)
        evaluaciones_a_procesar = queryset.exclude(resolutivo=nuevo_estado)
        
        count = 0
        correos_para_enviar = []

        # Abrimos UNA SOLA conexión para todo el lote
        with get_connection() as connection:
            for evaluacion in evaluaciones_a_procesar:
                
                # 1. Actualizamos y Guardamos (Dispara lógica de models.py y 3-strikes)
                evaluacion.resolutivo = nuevo_estado
                evaluacion.save() 
                
                # 2. Obtenemos datos del destinatario
                rep = evaluacion.proyecto.participacion_set.filter(es_representante=True).first()
                
                if rep and rep.alumno.correo_electronico:
                    folio = evaluacion.proyecto.folio
                    subject = ""
                    body = ""

                    # 3. Lógica de Contenido según el Estado
                    if nuevo_estado == 'APROBADO':
                        subject = f"🎉 ¡Felicidades! Proyecto APROBADO: {folio}"
                        body = (
                            f"Estimado alumno,\n\n"
                            f"Nos complace informarle que su proyecto con folio {folio} "
                            f"ha sido revisado y el dictamen es: APROBADO.\n\n"
                            f"¡Excelente trabajo!"
                        )

                    elif nuevo_estado == 'PENDIENTE':
                        subject = f"⚠️ Correcciones Requeridas - Proyecto: {folio}"
                        tipo = evaluacion.get_tipo_revision_display() # Ej. "Revisión de Forma"
                        obs = evaluacion.observaciones or "Sin observaciones detalladas."
                        body = (
                            f"Estimado alumno,\n\n"
                            f"Su proyecto {folio} ha recibido una revisión de tipo: {tipo}.\n"
                            f"Estado actual: PENDIENTE DE CORRECCIONES.\n\n"
                            f"📝 Observaciones del Evaluador:\n"
                            f"------------------------------------------------\n"
                            f"{obs}\n"
                            f"------------------------------------------------\n\n"
                            f"Favor de atender estas indicaciones y subir la nueva versión."
                        )

                    elif nuevo_estado == 'RECHAZADO':
                        subject = f"⛔ Proyecto NO APROBADO - Folio: {folio}"
                        obs = evaluacion.observaciones or "Sin observaciones detalladas."
                        body = (
                            f"Estimado alumno,\n\n"
                            f"Se le informa que la revisión reciente de su proyecto {folio} "
                            f"ha resultado en un dictamen: RECHAZADO.\n\n"
                            f"📝 Motivos / Observaciones:\n"
                            f"{obs}\n\n"
                            f"Si este es su tercer intento fallido, el proyecto será dado de baja automáticamente."
                        )

                    # 4. Empaquetamos el correo
                    if subject and body:
                        email = EmailMessage(
                            subject=subject,
                            body=body,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            to=[rep.alumno.correo_electronico],
                            connection=connection # Usamos la conexión compartida
                        )
                        correos_para_enviar.append(email)
                        count += 1
            
            # 5. Enviamos todo el paquete de una vez
            if correos_para_enviar:
                connection.send_messages(correos_para_enviar)

        self.message_user(request, f"✔ Se procesaron {count} evaluaciones al estado {nuevo_estado} y se enviaron sus notificaciones.")

    # =================================================================
    # ACCIONES (Botones visibles en el Admin)
    # =================================================================
    
    @admin.action(description="✅ Aprobar seleccionados (Enviar correo)")
    def accion_aprobar_masivo(self, request, queryset):
        self._procesar_cambio_masivo(request, queryset, 'APROBADO')

    @admin.action(description="⚠️ Solicitar Correcciones (Enviar Obs.)")
    def accion_correcciones_masivo(self, request, queryset):
        self._procesar_cambio_masivo(request, queryset, 'PENDIENTE')

    @admin.action(description="⛔ Rechazar seleccionados (Enviar Obs.)")
    def accion_rechazar_masivo(self, request, queryset):
        self._procesar_cambio_masivo(request, queryset, 'RECHAZADO')


    # =================================================================
    # MÉTODOS ESTÁNDAR (Get form, Save individual, Importar)
    # =================================================================

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj is None:
            form.base_fields["resolutivo"].initial = "NO_APLICA"
            form.base_fields["fecha_evaluacion"].initial = timezone.now()
        return form

    # Guarda individual (Edición manual de UN solo registro)
    def save_model(self, request, obj, form, change):
        resolutivo_anterior = None
        if change:
            try:
                resolutivo_anterior = Evaluaciones.objects.get(pk=obj.pk).resolutivo
            except Evaluaciones.DoesNotExist:
                resolutivo_anterior = None

        super().save_model(request, obj, form, change)
        obj.proyecto.refresh_from_db()

        # Lógica de envío individual (Mantenemos esto para ediciones manuales rápidas)
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
            total_exitos, lista_errores = importar_evaluaciones_forms()
            
            if total_exitos > 0:
                messages.success(request, f"✔ Éxito: Se crearon {total_exitos} evaluaciones nuevas.")
            
            if lista_errores:
                items_html = "".join([f"<li>{err}</li>" for err in lista_errores])
                mensaje_html = format_html(
                    "⚠ Se encontraron los siguientes problemas en el archivo:<br>"
                    "<ul style='margin-top:5px; margin-bottom:0;'>{}</ul>",
                    mark_safe(items_html)
                )
                messages.warning(request, mensaje_html)

            if total_exitos == 0 and not lista_errores:
                messages.info(request, "ℹ El proceso terminó correctamente, pero no había registros nuevos para importar.")

        except FileNotFoundError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"❌ Ocurrió un error inesperado: {e}")

        return redirect("..")