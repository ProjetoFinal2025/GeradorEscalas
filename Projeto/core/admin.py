from django.contrib import admin
from django.utils.safestring import mark_safe
from django.urls import path
from django.shortcuts import render, redirect, get_object_or_404
from datetime import date, timedelta
from django.utils import timezone
from django.template.defaulttags import register
from django.utils.html import format_html
from .forms import MilitarForm, ServicoForm, EscalaForm

from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin
# Permite alterar os seguintes modelos na admin view
from .models import Militar, Dispensa, Escala, Servico, Configuracao, Log, Feriado, EscalaMilitar
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

class EscalaMilitarInline(admin.TabularInline):
    model = EscalaMilitar
    extra = 0
    fields = ('display_militar', 'ordem_semana', 'ordem_fds')
    readonly_fields = ('display_militar',)
    can_delete = False

    #Removes the ability to add a new Militar in Escala View
    def has_add_permission(self, request, obj):
        # Return False => no "Add another" link in the inline
        return False

    def display_militar(self, obj):
        if not obj.pk:
            return "Selecione acima e salve."
        return f"{obj.militar.posto} {obj.militar.nome} ({str(obj.militar.nim).zfill(8)})"

    display_militar.short_description = "Militar"

@admin.action(description="Reset orders by NIM")
def reset_orders_by_nim(modeladmin, request, queryset):

    for escala in queryset:
        esc_mils = EscalaMilitar.objects.filter(escala=escala).select_related('militar').order_by('militar__nim')
        for i, em in enumerate(esc_mils, start=1):
            em.ordem_semana = i
            em.ordem_fds = i
            em.save()

class EscalaAdmin(admin.ModelAdmin):
    # Adiciona o Inline na view AdminEscala
    inlines = [EscalaMilitarInline]
    actions = [reset_orders_by_nim]
    form = EscalaForm
    list_display = ['id', 'servico', 'data', 'e_escala_b']
    list_filter = ('servico', 'data', 'e_escala_b')
    search_fields = ('servico__nome', 'data')
    date_hierarchy = 'data'

    def save_model(self, request, obj, form, change):
        # save Escala
        super().save_model(request, obj, form, change)

        # create a row for each Militar in the related Servico
        if obj.servico:
            servico_militares = obj.servico.militares.all()
            
            # Atribuir militares à escala atual (A ou B)
            for mil in servico_militares:
                EscalaMilitar.objects.get_or_create(
                    escala=obj,
                    militar=mil,
                    defaults={
                        'ordem_semana': EscalaMilitar.objects.filter(escala=obj).count() + 1,
                        'ordem_fds': EscalaMilitar.objects.filter(escala=obj).count() + 1
                    }
                )
            
            # Se o serviço tem escala B e esta é uma escala A, criar a escala B correspondente
            if obj.servico.tem_escala_B and not obj.e_escala_b:
                # Criar ou atualizar a escala B correspondente
                escala_b, created = Escala.objects.get_or_create(
                    servico=obj.servico,
                    data=obj.data,
                    e_escala_b=True
                )
                
                # Atribuir militares à escala B
                for mil in servico_militares:
                    EscalaMilitar.objects.get_or_create(
                        escala=escala_b,
                        militar=mil,
                        defaults={
                            'ordem_semana': EscalaMilitar.objects.filter(escala=escala_b).count() + 1,
                            'ordem_fds': EscalaMilitar.objects.filter(escala=escala_b).count() + 1
                        }
                    )

    # Allows to reset based on NIM for Escala ordem
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        if request.method == "POST" and "_reset_ordem" in request.POST:
            escala = self.get_object(request, object_id)
            if escala:
                # Reset ordem by NIM
                related = escala.militares_info.select_related('militar').order_by('militar__nim')
                for i, em in enumerate(related, start=1):
                    em.ordem_semana = i
                    em.ordem_fds = i
                    em.save()
                self.message_user(request, "Ordem redefinida com sucesso.")
                return redirect(request.path)

        extra_context = extra_context or {}
        extra_context["custom_reset_button"] = True
        return super().changeform_view(request, object_id, form_url, extra_context)


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
        servico_id = request.GET.get('servico')
        servico_selecionado = None
        servicos = Servico.objects.filter(ativo=True)
        
        if servico_id:
            servico_selecionado = get_object_or_404(Servico, id=servico_id, ativo=True)
            servicos = [servico_selecionado]
        
        hoje = timezone.now().date()
        # Calcular dias até ao final do ano
        ultimo_dia_ano = date(hoje.year, 12, 31)
        dias_restantes = (ultimo_dia_ano - hoje).days
        
        # Obter lista de feriados
        feriados = obter_feriados(hoje, ultimo_dia_ano)
        
        # Agrupar dias por mês
        dias_por_mes = {}
        dias = []
        data_atual = hoje
        
        while data_atual <= ultimo_dia_ano:
            mes = data_atual.replace(day=1)
            if mes not in dias_por_mes:
                dias_por_mes[mes] = []
            
            e_fim_semana = data_atual.weekday() >= 5  # 5 = Sábado, 6 = Domingo
            e_feriado = data_atual in feriados
            
            dia_info = {
                'data': data_atual, 
                'dia_semana': data_atual.strftime('%A'),
                'e_fim_semana': e_fim_semana,
                'e_feriado': e_feriado
            }
            
            dias_por_mes[mes].append(dia_info)
            dias.append(dia_info)
            data_atual += timedelta(days=1)
        
        mapa_dispensas = {}
        for servico in servicos:
            militares = servico.militares.all()
            dispensas_servico = {}
            
            # Initialize summary data
            resumo = {
                'dispensados': {},
                'disponiveis': {},
                'total': {}
            }
            
            for militar in militares:
                dispensas = {}
                for dia in dias:
                    dispensa = Dispensa.objects.filter(
                        militar=militar,
                        data_inicio__lte=dia['data'],
                        data_fim__gte=dia['data']
                    ).first()
                    if dispensa:
                        dispensas[dia['data']] = dispensa
                        # Update summary for dispensados
                        if dia['data'] not in resumo['dispensados']:
                            resumo['dispensados'][dia['data']] = 0
                        resumo['dispensados'][dia['data']] += 1
                    
                    # Update total
                    if dia['data'] not in resumo['total']:
                        resumo['total'][dia['data']] = 0
                    resumo['total'][dia['data']] += 1
                
                dispensas_servico[militar] = dispensas
            
            # Calculate disponiveis for each day
            for dia in dias:
                total = resumo['total'].get(dia['data'], 0)
                dispensados = resumo['dispensados'].get(dia['data'], 0)
                resumo['disponiveis'][dia['data']] = total - dispensados
            
            mapa_dispensas[servico] = {
                'militares': dispensas_servico,
                'resumo': resumo
            }
        
        return render(request, 'admin/mapa_dispensas_test.html', {
            'mapa_dispensas': mapa_dispensas,
            'dias': dias,
            'dias_por_mes': dias_por_mes,
            'servicos': Servico.objects.filter(ativo=True),
            'servico_selecionado': servico_selecionado
        })

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
class PrevisaoEscalasProxy(Escala):
    class Meta:
        proxy = True
        verbose_name = "Previsão de Escalas"
        verbose_name_plural = "Previsão de Escalas"

# Criar instância do admin site customizado
admin_site = GeradorEscalasAdminSite(name='admin')
admin_site.register(User, UserAdmin)
admin_site.register(Group, GroupAdmin)

# Registrar os modelos no admin site customizado
admin_site.register(Militar, MilitarAdmin)
admin_site.register(Servico, ServicoAdmin)
admin_site.register(Escala, EscalaAdmin)
admin_site.register(Dispensa, DispensaAdmin)
admin_site.register(Configuracao, ConfiguracaoAdmin)
admin_site.register(Feriado, FeriadoAdmin)
admin_site.register(Log)
admin_site.register(PrevisaoEscalasProxy, PrevisaoEscalasAdmin)

# Registrar a Previsão de Escalas como um modelo proxy

