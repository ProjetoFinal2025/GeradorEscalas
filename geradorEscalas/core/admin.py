from django.contrib import admin
from django.utils.safestring import mark_safe

from .forms import MilitarForm, ServicoForm, EscalaForm
# Permite alterar os seguintes modelos na admin view
from .models import Militar, Dispensa, Escala, Servico, Configuracao, Log

class MilitarAdmin(admin.ModelAdmin):
    form = MilitarForm
    list_display = ('nome', 'posto', 'nim', 'listar_servicos', 'listar_escalas')
    # Remove a habilidade de mudar o Utilizador de um militar
    readonly_fields = ['user', 'listar_servicos', 'listar_escalas','listar_dispensas']
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
    list_display = ['id', 'servico', 'data', 'e_escala_b']
    readonly_fields = ['ver_militares_do_servico']


    def ver_militares_do_servico(self, obj):
        militares = obj.servico.militares.all()
        if not militares.exists():
            return "Nenhum militar atribuído a esta escala"
        return ", ".join(f"{m.posto} {m.nome} ({str(m.nim).zfill(8)})" for m in militares)

    ver_militares_do_servico.short_description = "Militares na Escala"

admin.site.register(Militar,MilitarAdmin)
admin.site.register(Dispensa)
admin.site.register(Escala, EscalaAdmin)
admin.site.register(Servico, ServicoAdmin)
admin.site.register(Configuracao)
admin.site.register(Log)
