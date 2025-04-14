from django.contrib import admin
from django.utils.safestring import mark_safe
from django.urls import path, reverse
from django.shortcuts import render
from django.db.models import Q
from datetime import date, timedelta, time
from django.template.defaulttags import register
from django.utils.html import format_html

from .forms import MilitarForm, ServicoForm, EscalaForm
# Permite alterar os seguintes modelos na admin view
from .models import Militar, Dispensa, Escala, Servico, Configuracao, Log, Feriado
from .views import obter_feriados

# Configuração do Admin Site
class GeradorEscalasAdminSite(admin.AdminSite):
    site_header = 'Gerador de Escalas'
    site_title = 'Gerador de Escalas'
    index_title = 'Administração do Sistema'

    def get_app_list(self, request):
        app_list = super().get_app_list(request)
        
        # Encontrar a app 'core'
        core_app = next((app for app in app_list if app['app_label'] == 'core'), None)
        
        if core_app:
            # Criar nova seção para Previsões
            previsoes_section = {
                'name': 'PREVISÕES',
                'app_label': 'core',
                'app_url': '/admin/core/',
                'has_module_perms': True,
                'models': [
                    {
                        'name': 'Previsão de Escalas',
                        'object_name': 'previsaoescalasproxy',
                        'admin_url': '/admin/core/previsaoescalasproxy/',
                        'view_only': False,
                    }
                ],
            }
            
            # Adicionar a nova seção após a app 'core'
            index = app_list.index(core_app)
            app_list.insert(index + 1, previsoes_section)
        
        return app_list

# Criar instância do admin site customizado
admin_site = GeradorEscalasAdminSite(name='admin')

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
    form = EscalaForm
    list_display = ['id', 'servico', 'data', 'e_escala_b']
    list_filter = ('servico', 'data', 'e_escala_b')
    search_fields = ('servico__nome', 'data')
    date_hierarchy = 'data'
    readonly_fields = ['ver_militares_do_servico']

    def ver_militares_do_servico(self, obj):
        militares = obj.servico.militares.all()
        if not militares.exists():
            return "Nenhum militar atribuído a esta escala"

        rows = ""
        for m in militares:
            rows += f"""
                <tr>
                    <td style="padding: 8px;">{m.posto}</td>
                    <td style="padding: 8px;">{m.nome}</td>
                    <td style="padding: 8px;">{str(m.nim).zfill(8)}</td>
                </tr>
            """

        return format_html(f"""
            <div style="width: 100%;">
                <table style="
                    width: 100%;
                    border-collapse: collapse;
                    table-layout: fixed;
                    text-align: left;
                    background-color: #fff;
                    border: 1px solid #ccc;
                ">
                    <thead style="background-color: #f9f9f9;">
                        <tr>
                            <th style='padding: 8px; width: 20%;'>Posto</th>
                            <th style='padding: 8px; width: 50%;'>Nome</th>
                            <th style='padding: 8px; width: 30%;'>NIM</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                </table>
            </div>
        """)

    ver_militares_do_servico.short_description = "Militares na Escala"

class PrevisaoEscalasAdmin(admin.ModelAdmin):
    change_list_template = 'admin/core/escala/previsao.html'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('', self.admin_site.admin_view(self.previsao_view), name='core_previsaoescalasproxy_changelist'),
        ]
        return custom_urls + urls

    def previsao_view(self, request):
        # Obter o serviço selecionado ou o primeiro serviço ativo
        servico_id = request.GET.get('servico')
        if servico_id:
            servico = Servico.objects.get(id=servico_id)
        else:
            servico = Servico.objects.filter(ativo=True).first()

        # Obter a data final da previsão
        hoje = date.today()
        data_fim_str = request.GET.get('data_fim')
        if data_fim_str:
            try:
                data_fim = date.fromisoformat(data_fim_str)
            except ValueError:
                data_fim = hoje + timedelta(days=30)
        else:
            data_fim = hoje + timedelta(days=30)

        # Obter feriados no período
        feriados = obter_feriados(hoje, data_fim)
        
        # Gerar lista de datas com suas escalas
        datas = []
        data_atual = hoje

        while data_atual <= data_fim:
            # Buscar escala existente para esta data
            escala = Escala.objects.filter(
                servico=servico,
                data=data_atual,
            ).first()

            # Verificar se é fim de semana ou feriado
            e_fim_semana = data_atual.weekday() >= 5
            e_feriado = data_atual in feriados

            datas.append({
                'data': data_atual,
                'escala': escala,
                'e_fim_semana': e_fim_semana,
                'e_feriado': e_feriado,
                'tipo_dia': 'feriado' if e_feriado else ('fim_semana' if e_fim_semana else 'util')
            })
            
            data_atual += timedelta(days=1)

        # Buscar todos os serviços ativos para o seletor
        servicos = Servico.objects.filter(ativo=True)

        context = {
            'title': f'Previsão de Escalas - {servico.nome}',
            'servico': servico,
            'servicos': servicos,
            'datas': datas,
            'hoje': hoje,
            'data_fim': data_fim,
            'opts': self.model._meta,
            'cl': self,
            'is_popup': False,
            'has_add_permission': self.has_add_permission(request),
            'has_change_permission': self.has_change_permission(request),
            'has_delete_permission': self.has_delete_permission(request),
        }

        return render(request, 'admin/core/escala/previsao.html', context)

    class Meta:
        verbose_name = "Previsão de Escalas"
        verbose_name_plural = "Previsão de Escalas"

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
        dias_restantes = (date(hoje.year, 12, 31) - hoje).days
        
        # Obter todos os serviços ativos
        servicos = Servico.objects.filter(ativo=True)
        
        # Se um serviço foi selecionado, filtrar as dispensas
        if servico_id:
            servico = Servico.objects.get(id=servico_id)
            militares = servico.militares.all()
            dispensas = Dispensa.objects.filter(
                militar__in=militares,
                data_inicio__gte=hoje,
                data_inicio__lte=hoje + timedelta(days=dias_restantes)
            ).order_by('data_inicio')
        else:
            dispensas = Dispensa.objects.filter(
                data_inicio__gte=hoje,
                data_inicio__lte=hoje + timedelta(days=dias_restantes)
            ).order_by('data_inicio')
        
        # Agrupar dispensas por serviço
        mapa_dispensas = {}
        for servico in servicos:
            militares_servico = servico.militares.all()
            dispensas_servico = dispensas.filter(militar__in=militares_servico)
            if dispensas_servico.exists():
                mapa_dispensas[servico] = dispensas_servico
        
        context = {
            'title': 'Mapa de Dispensas',
            'mapa_dispensas': mapa_dispensas,
            'servicos': servicos,
            'servico_selecionado': servico_id,
            'hoje': hoje,
            'dias_restantes': dias_restantes,
        }
        
        return render(request, 'admin/mapa_dispensas.html', context)

class ConfiguracaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'inicio_semana')
    
    fieldsets = (
        ('Configurações Gerais', {
            'fields': ('inicio_semana',)
        }),
    )

class FeriadoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'data', 'tipo')
    list_filter = ('tipo',)
    search_fields = ('nome',)
    date_hierarchy = 'data'

# Registrar os modelos no admin site customizado
admin_site.register(Militar, MilitarAdmin)
admin_site.register(Servico, ServicoAdmin)
admin_site.register(Escala, EscalaAdmin)
admin_site.register(Dispensa, DispensaAdmin)
admin_site.register(Configuracao, ConfiguracaoAdmin)
admin_site.register(Feriado, FeriadoAdmin)
admin_site.register(Log)

# Registrar a Previsão de Escalas como um modelo proxy
class PrevisaoEscalasProxy(Escala):
    class Meta:
        proxy = True
        verbose_name = "Previsão de Escalas"
        verbose_name_plural = "Previsão de Escalas"

admin_site.register(PrevisaoEscalasProxy, PrevisaoEscalasAdmin)
