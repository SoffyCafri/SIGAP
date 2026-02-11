from django import forms
from django.contrib import admin, messages
from django.core.mail import send_mail
from django.urls import path
from django.shortcuts import redirect
from django.utils.html import format_html
from django.conf import settings
from .models import Proyecto, Formato1, Participacion, Prorroga
from evaluation.models import Evaluaciones

# --------------------------------------------------------------------
# 1. TU FORMULARIO PERSONALIZADO (Esto ya lo tienes bien)
# --------------------------------------------------------------------
class ProyectoForm(forms.ModelForm):
    OPCIONES_NIVEL = [
        ('INTERMEDIO', 'INTERMEDIO'),
        ('AVANZADO', 'AVANZADO'),
    ]

    nivel_competencia = forms.MultipleChoiceField(
        choices=OPCIONES_NIVEL,
        widget=forms.CheckboxSelectMultiple, # Los checkboxes
        required=False,
        label="Módulos Registrados"
    )

    class Meta:
        model = Proyecto
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convertir texto "A, B" a lista ['A', 'B'] para visualización
        if self.instance and self.instance.pk and self.instance.nivel_competencia:
            try:
                vals = self.instance.nivel_competencia.split(',')
                self.initial['nivel_competencia'] = [x.strip() for x in vals]
            except:
                self.initial['nivel_competencia'] = []

    def clean_nivel_competencia(self):
        # Convertir lista ['A', 'B'] a texto "A, B" para guardado
        data = self.cleaned_data['nivel_competencia']
        if not data:
            return None
        return ", ".join(data)

# --- Inlines ---

class Formato1Inline(admin.StackedInline):
    model = Formato1
    can_delete = False
    verbose_name = "Documentación (Formato 1)"
    verbose_name_plural = "Documentación Inicial"

class ParticipacionInline(admin.TabularInline):
    model = Participacion
    extra = 1
    autocomplete_fields = ['alumno']

class ProrrogaInline(admin.TabularInline):
    model = Prorroga
    extra = 0

class EvaluacionesInline(admin.TabularInline):
    model = Evaluaciones
    extra = 0
    readonly_fields = ('fecha_evaluacion', 'evaluador', 'tipo_revision', 'resolutivo', 'observaciones')
    can_delete = False


# --- Registros Principales ---

@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):

    form = ProyectoForm
    
    list_display = (
        'folio', 'titulo', 'asesor', 'evaluador', 'modalidad',
        'calendario_registro', 'dictamen',
        'boton_enviar_correo', 'boton_enviar_correo_evaluador',
    )

    list_filter = (
        'modalidad', 'calendario_registro', 'dictamen', 'asesor', 'evaluador'
    )

    search_fields = (
        'folio', 'titulo', 'asesor__nombre_completo',
        'evaluador__nombre_completo', 'participantes__nombre_completo'
    )

    inlines = [
        Formato1Inline,
        ParticipacionInline,
        ProrrogaInline,
        EvaluacionesInline
    ]

    # --- Botones personalizados ---
    def boton_enviar_correo(self, obj):
        return format_html(
            '<a class="button" href="enviar-correo/{}/" '
            'style="padding:5px 10px; background:#0b6efd; color:white; '
            'border-radius:6px; text-decoration:none;">📨 Enviar correo</a>',
            obj.pk
        )
    boton_enviar_correo.short_description = "Acción"

    def boton_enviar_correo_evaluador(self, obj):
        return format_html(
            '<a class="button" href="enviar-correo-evaluador/{}/" '
            'style="padding:5px 10px; background:#198754; color:white; '
            'border-radius:6px; text-decoration:none;">📧 Enviar a Evaluador</a>',
            obj.pk
        )
    boton_enviar_correo_evaluador.short_description = "Correo Evaluador"

    # --- URLs Personalizadas ---
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('enviar-correo/<str:folio>/', self.admin_site.admin_view(self.enviar_correo), name='enviar_correo'),
            path('enviar-correo-evaluador/<str:folio>/', self.admin_site.admin_view(self.enviar_correo_evaluador), name='enviar_correo_evaluador'),
            path('importar-forms/', self.admin_site.admin_view(self.importar_forms), name='importar_forms_admin'),
        ]
        return custom_urls + urls

    # --- LÓGICA DE NEGOCIO ---

    def importar_forms(self, request):
        from django.core.management import call_command
        try:
            call_command("importar_forms")
            messages.success(request, "✔ Importación desde Google Forms ejecutada correctamente.")
        except Exception as e:
            messages.error(request, f"❌ Error durante la importación: {e}")
        return redirect(request.META.get('HTTP_REFERER', 'admin:index'))

    def enviar_correo(self, request, folio):
        proyecto = Proyecto.objects.get(pk=folio)
        destinatarios = []

        if proyecto.asesor and proyecto.asesor.correo_electronico:
            destinatarios.append(proyecto.asesor.correo_electronico)
        if proyecto.evaluador and proyecto.evaluador.correo_evaluador:
            destinatarios.append(proyecto.evaluador.correo_evaluador)
        
        for participacion in proyecto.participacion_set.all():
            alumno = participacion.alumno
            if alumno and alumno.correo_electronico:
                destinatarios.append(alumno.correo_electronico)

        destinatarios = list(set(destinatarios))

        if not destinatarios:
            messages.error(request, "❌ No hay correos registrados para este proyecto.")
            return redirect(request.META.get('HTTP_REFERER', 'admin:index'))

        asunto = f"Notificación del Proyecto {proyecto.folio}"
        mensaje = (
            f"Estimados participantes,\n\n"
            f"Este es un aviso relacionado con el proyecto '{proyecto.titulo}' "
            f"(folio: {proyecto.folio}).\n\n"
            f"Atentamente,\nComité de Evaluación"
        )

        send_mail(asunto, mensaje, None, destinatarios, fail_silently=False)
        messages.success(request, f"✅ Correo enviado correctamente a los participantes.")
        return redirect(request.META.get('HTTP_REFERER', 'admin:index'))

    # ✅ AQUÍ ESTÁ LA CORRECCIÓN IMPORTANTE
    def enviar_correo_evaluador(self, request, folio):
        """
        Envía los detalles técnicos del proyecto (Formato 1) al evaluador asignado.
        """
        proyecto = Proyecto.objects.get(pk=folio)

        # 1. Validar Evaluador
        if not proyecto.evaluador or not proyecto.evaluador.correo_evaluador:
            messages.error(request, "❌ Este proyecto no tiene un evaluador con correo asignado.")
            return redirect(request.META.get('HTTP_REFERER', 'admin:index'))

        # 2. Validar Documentación (Formato 1)
        # Usamos el related_name='formato1_data' definido en el modelo
        if not hasattr(proyecto, 'formato1_data'):
            messages.error(request, "❌ Error: El proyecto no tiene la documentación (Formato 1) registrada. Llene los datos primero.")
            return redirect(request.META.get('HTTP_REFERER', 'admin:index'))

        # 3. Preparar Datos
        formato = proyecto.formato1_data 
        destinatario = proyecto.evaluador.correo_evaluador
        asunto = f"[Evaluación] Asignación de Proyecto {proyecto.folio}"

        # Construcción del cuerpo del correo
        mensaje = (
            f"Estimado/a Evaluador/a,\n\n"
            f"Se le ha asignado el siguiente proyecto para su revisión en SIGAP:\n\n"
            f"========================================\n"
            f"DATOS GENERALES\n"
            f"========================================\n"
            f"• Folio: {proyecto.folio}\n"
            f"• Título: {proyecto.titulo}\n\n"
            f"========================================\n"
            f"DOCUMENTACIÓN TÉCNICA\n"
            f"========================================\n\n"
            f"--- INTRODUCCIÓN ---\n{formato.introduccion}\n\n"
            f"--- JUSTIFICACIÓN ---\n{formato.justificacion}\n\n"
            f"--- OBJETIVO ---\n{formato.objetivo}\n\n"
            f"--- RESUMEN ---\n{formato.resumen}\n\n"
            f"========================================\n\n"
            f"Por favor ingrese al formulario correspondiente para hacer la revisión.\n\n"
            f"Atentamente,\n"
            f"Comité de Evaluación"
        )

        try:
            send_mail(
                subject=asunto,
                message=mensaje,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[destinatario],
                fail_silently=False,
            )
            messages.success(request, f"✅ Correo enviado exitosamente al evaluador del proyecto {proyecto.folio}.")
        except Exception as e:
            messages.error(request, f"❌ Error al enviar el correo: {e}")

        return redirect(request.META.get('HTTP_REFERER', 'admin:index'))


@admin.register(Participacion)
class ParticipacionAdmin(admin.ModelAdmin):
    list_display = ('proyecto', 'alumno', 'es_representante')
    list_filter = ('es_representante',)
    autocomplete_fields = ['proyecto', 'alumno']


@admin.register(Formato1)
class Formato1Admin(admin.ModelAdmin):
    # Ajustamos esto porque 'folio' ya no es un campo directo visible fácilmente
    list_display = ('proyecto', 'resumen_corto') 
    search_fields = ('proyecto__folio', 'introduccion')

    def resumen_corto(self, obj):
        return obj.resumen[:50] + "..."