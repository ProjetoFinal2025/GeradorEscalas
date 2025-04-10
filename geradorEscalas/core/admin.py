from django.contrib import admin
from django.utils.safestring import mark_safe

from .forms import MilitarForm, ServicoForm
# Permite alterar os seguintes modelos na admin view
from .models import Militar, Dispensa, Escala, Servico, Configuracao, Log

class MilitarAdmin(admin.ModelAdmin):
    form = MilitarForm
    # Remove a habilidade de mudar o NIM de um militar
    readonly_fields = ['user']

class ServicoAdmin(admin.ModelAdmin):
    form = ServicoForm
    readonly_fields = ['ver_escalas']

    ## TEMP? Permite ver as escalas que o Servico tem
    def ver_escalas(self, obj):
        if not obj.pk:
            return "O serviço ainda não foi salvo."

        escalas = Escala.objects.filter(servico=obj)  # ou servico_principal=obj
        if not escalas.exists():
            return "Nenhuma escala atribuída."

        html = "<ul>"
        for escala in escalas:
            html += f"<li>{escala}</li>"  # usa o __str__ da Escala
        html += "</ul>"
        return mark_safe(html)

    ver_escalas.short_description = "Escalas atribuídas"

class EscalaAdmin(admin.ModelAdmin):
    readonly_fields = ['nomes_militares']
    list_display = ['id', 'data', 'servico', 'e_escala_b', 'nomes_militares']

admin.site.register(Militar,MilitarAdmin)
admin.site.register(Dispensa)
admin.site.register(Escala,EscalaAdmin)
admin.site.register(Servico, ServicoAdmin)
admin.site.register(Configuracao)
admin.site.register(Log)
