from django.contrib import admin
from .forms import MilitarForm, ServicoForm
# Permite alterar os seguintes modelos na admin view
from .models import Militar, Dispensa, Escala, Servico, Configuracao, Log

class MilitarAdmin(admin.ModelAdmin):
    form = MilitarForm
    # Remove a habilidade de mudar o NIM de um militar
    readonly_fields = ['user']

class ServicoAdmin(admin.ModelAdmin):
    form = ServicoForm

admin.site.register(Militar,MilitarAdmin)
admin.site.register(Dispensa)
admin.site.register(Escala)
admin.site.register(Servico, ServicoAdmin)
admin.site.register(Configuracao)
admin.site.register(Log)
