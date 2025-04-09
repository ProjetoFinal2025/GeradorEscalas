from django.contrib import admin

# Permite alterar os seguintes modelos na admin view
from .models import Militar, Dispensa, Escala, Servico, Configuracao, Log

admin.site.register(Militar)
admin.site.register(Dispensa)
admin.site.register(Escala)
admin.site.register(Servico)
admin.site.register(Configuracao)
admin.site.register(Log)
