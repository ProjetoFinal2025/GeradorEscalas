from django.contrib import admin
from django.utils.safestring import mark_safe
from django.urls import path, reverse
from django.shortcuts import render
from django.db.models import Q
from datetime import date, timedelta, time
from django.template.defaulttags import register

from .forms import MilitarForm, ServicoForm, EscalaForm
# Permite alterar os seguintes modelos na admin view
from .models import Militar, Dispensa, Escala, Servico, Configuracao, Log, Feriado
from .views import obter_feriados

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

class MilitarAdmin(admin.ModelAdmin):
    form = MilitarForm
    list_display = ('nome', 'posto', 'nim', 'listar_servicos', 'listar_escalas')
    # Remove a habilidade de mudar o Utilizador de um militar
    readonly_fields = ['user', 'listar_servicos', 'listar_escalas','listar_dispensas']

class ServicoAdmin(admin.ModelAdmin):
    form = ServicoForm
    list_display = ('nome', 'hora_inicio', 'hora_fim', 'n_elementos', 'tem_escala_B', 'armamento', 'ativo')
    list_filter = ('ativo', 'tem_escala_B', 'armamento')
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'ativo')
        }),
        ('Configurações do Serviço', {
            'fields': ('hora_inicio', 'hora_fim', 'n_elementos', 'tem_escala_B', 'armamento'),
            'classes': ('wide',)
        }),
        ('Militares', {
            'fields': ('militares',),
            'classes': ('wide',)
        }),
    )
    filter_horizontal = ('militares',)
    readonly_fields = ['ver_escalas']

    def ver_escalas(self, obj):
        if not obj.pk:
            return "O serviço ainda não foi salvo."

        escalas = Escala.objects.filter(servico=obj)
        if not escalas.exists():
            return "Nenhuma escala atribuída."

        html = "<ul>"
        for escala in escalas:
            html += f"<li>{escala}</li>"
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

class DispensaAdmin(admin.ModelAdmin):
    list_display = ('militar', 'data_inicio', 'data_fim', 'motivo', 'servico_atual')
    list_filter = ('militar__servicos', 'data_inicio', 'data_fim')
    search_fields = ('militar__nome', 'militar__nim', 'motivo')
    date_hierarchy = 'data_inicio'
    
    def servico_atual(self, obj):
        servicos = obj.militar.servicos.filter(ativo=True)
        return ", ".join(str(s) for s in servicos)
    servico_atual.short_description = "Serviço Atual"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_mapa_link'] = True
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('mapa-dispensas/', self.admin_site.admin_view(self.mapa_dispensas_view), name='mapa-dispensas'),
        ]
        return custom_urls + urls

    def mapa_dispensas_view(self, request):
        # Obter o serviço selecionado do filtro
        servico_id = request.GET.get('servico', None)
        
        # Obter o dia atual e calcular dias até ao final do ano
        hoje = date.today()
        ultimo_dia_ano = date(hoje.year, 12, 31)
        dias = [hoje + timedelta(days=x) for x in range((ultimo_dia_ano - hoje).days + 1)]
        
        # Obter feriados
        feriados = obter_feriados(hoje.year)
        
        # Dicionário com nomes dos meses em português
        meses_pt = {
            1: 'janeiro',
            2: 'fevereiro',
            3: 'março',
            4: 'abril',
            5: 'maio',
            6: 'junho',
            7: 'julho',
            8: 'agosto',
            9: 'setembro',
            10: 'outubro',
            11: 'novembro',
            12: 'dezembro'
        }
        
        # Criar dicionário com informações de cada dia
        dias_info = []
        for dia in dias:
            e_feriado = dia in feriados
            e_fim_semana = dia.weekday() >= 5
            dias_info.append({
                'data': dia,
                'e_feriado': e_feriado,
                'e_fim_semana': e_fim_semana,
                'mes': meses_pt[dia.month]
            })
        
        # Obter todas as dispensas que se sobrepõem com o período
        dispensas = Dispensa.objects.filter(
            Q(data_inicio__lte=ultimo_dia_ano) & Q(data_fim__gte=hoje)
        )
        
        # Filtrar por serviço se selecionado
        if servico_id:
            dispensas = dispensas.filter(militar__servicos__id=servico_id)
        
        # Agrupar dispensas por serviço
        servicos = Servico.objects.filter(ativo=True)
        mapa_dispensas = {}
        
        for servico in servicos:
            servico_dispensas = dispensas.filter(militar__servicos=servico)
            total_militares = servico.militares.count()
            
            if servico_dispensas.exists() or total_militares > 0:
                # Para cada militar do serviço, criar um dicionário de dispensas por dia
                militares_com_dispensas = {}
                totais_por_dia = {dia: 0 for dia in dias}
                
                for militar in servico.militares.all():
                    dispensas_militar = {}
                    for dia in dias:
                        dispensa = servico_dispensas.filter(
                            militar=militar,
                            data_inicio__lte=dia,
                            data_fim__gte=dia
                        ).first()
                        if dispensa:
                            dispensas_militar[dia] = dispensa
                            totais_por_dia[dia] += 1
                    if dispensas_militar:
                        militares_com_dispensas[militar] = dispensas_militar
                
                # Calcular militares disponíveis por dia
                disponiveis_por_dia = {
                    dia: total_militares - totais_por_dia[dia]
                    for dia in dias
                }
                
                mapa_dispensas[servico] = {
                    'militares': militares_com_dispensas,
                    'totais_dispensados': totais_por_dia,
                    'total_militares': total_militares,
                    'disponiveis': disponiveis_por_dia
                }
        
        context = {
            'title': 'Mapa de Dispensas',
            'mapa_dispensas': mapa_dispensas,
            'servicos': servicos,
            'servico_selecionado': int(servico_id) if servico_id else None,
            'dias': dias_info,
            'hoje': hoje,
            'meses_pt': meses_pt,
        }
        
        return render(request, 'admin/mapa_dispensas.html', context)

class ConfiguracaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'inicio_semana')
    
    fieldsets = (
        ('Configurações de Calendário', {
            'fields': ('inicio_semana',),
            'classes': ('wide',)
        }),
    )

class FeriadoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'data', 'tipo')
    list_filter = ('tipo',)
    search_fields = ('nome',)
    date_hierarchy = 'data'

admin.site.register(Militar, MilitarAdmin)
admin.site.register(Dispensa, DispensaAdmin)
admin.site.register(Escala, EscalaAdmin)
admin.site.register(Servico, ServicoAdmin)
admin.site.register(Configuracao, ConfiguracaoAdmin)
admin.site.register(Feriado, FeriadoAdmin)
admin.site.register(Log)
