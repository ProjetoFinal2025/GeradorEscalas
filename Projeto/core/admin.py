from django.contrib import admin, messages
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import path
from reversion.admin import VersionAdmin
from .models import *
from .utils import obter_feriados
from django.utils import timezone
from django.template.defaulttags import register
from .forms import MilitarForm, ServicoForm, EscalaForm
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe
from .services.pdf_exports import gerar_pdf_escala
from django.http import FileResponse, Http404
from .services.escala_service import EscalaService

# Permite alterar os seguintes modelos na admin view
from .models import Militar, Dispensa, Escala, Servico, Configuracao, Log, Feriado, EscalaMilitar, RegraNomeacao

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

class MilitarAdmin(VersionAdmin):
    form = MilitarForm
    list_display = ('nome', 'posto', 'nim', 'listar_servicos', 'listar_escalas')
    # Remove a habilidade de mudar o Utilizador de um militar
    readonly_fields = ['user', 'listar_servicos', 'listar_escalas','listar_dispensas']

class ServicoAdmin(VersionAdmin):
    form = ServicoForm
    list_display = (
        'nome', 'hora_inicio', 'hora_fim', 'n_elementos',
        'tipo_escalas', 'armamento', 'ativo',
        'escalas_col',
    )
    list_filter = ('ativo', 'tipo_escalas', 'armamento')
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'ativo')
        }),
        ('Configurações do Serviço', {
            'fields': ('hora_inicio', 'hora_fim', 'n_elementos', 'tipo_escalas', 'armamento'),
            'classes': ('wide',)
        }),
        ('Militares', {
            'fields': ('militares',),
            'classes': ('wide',)
        }),
    )
    filter_horizontal = ('militares',)
    readonly_fields = ['ver_escalas']

    # Shows Escalas in Service View
    def escalas_col(self, obj):
        if hasattr(obj, "escalas"):
            qs = obj.escalas.all()  # related_name='escalas'
        else:
            qs = Escala.objects.filter(servico=obj)  # related_name='+' (no reverse)

        if not qs.exists():
            return "—"

        items = format_html_join(
            '',
            '<li><a href="{}">{}</a></li>',
            (
                (
                    reverse('admin:core_escala_change', args=(e.pk,)),
                    str(e),
                )
                for e in qs
            )
        )
        return mark_safe(
            f'<details><summary>{qs.count()} escala(s)</summary>'
            f'<ul style="margin-left:1rem">{items}</ul>'
            f'</details>'
        )

    escalas_col.short_description = "Escalas"

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

class EscalaAdmin(VersionAdmin):
    # Adiciona o Inline na view AdminEscala
    inlines = [EscalaMilitarInline]
    actions = [reset_orders_by_nim]
    form = EscalaForm
    list_display = ("id", "servico", "data", "e_escala_b")
    list_filter   = ("servico", "data", "e_escala_b")
    search_fields = ('servico__nome', 'data')
    date_hierarchy = 'data'

    change_form_template = "admin/core/escala/change_form.html"  # NEW

    def get_urls(self):

        urls = super().get_urls()
        custom = [
            path(
                "<path:object_id>/export-pdf/",
                self.admin_site.admin_view(self.export_militares_pdf),
                name="core_escala_export_pdf",
            ),
        ]
        return custom + urls

    def export_militares_pdf(self, request, object_id, *args, **kwargs):
        escala = self.get_object(request, object_id)
        if not escala:
            raise Http404
        pdf_buffer = gerar_pdf_escala(escala)
        filename = f"escala_{escala.pk}_militares.pdf"
        return FileResponse(pdf_buffer, as_attachment=True, filename=filename)

    def changeform_view(self, request, object_id=None,
                        form_url="", extra_context=None):

        #  handle the special POST that resets ordem
        if request.method == "POST" and "_reset_ordem" in request.POST and object_id:
            escala = self.get_object(request, object_id)
            if escala:
                related = (escala.militares_info
                           .select_related("militar")
                           .order_by("militar__nim"))
                for i, em in enumerate(related, start=1):
                    em.ordem_semana = i
                    em.ordem_fds = i
                    em.save()
                self.message_user(request, "Ordem redefinida com sucesso.")
                return redirect(request.path)

        # supply both variables to the template
        extra_context = extra_context or {}
        extra_context["custom_reset_button"] = True
        if object_id:
            extra_context["export_pdf_url"] = reverse(
                "admin:core_escala_export_pdf", args=[object_id]
            )

        return super().changeform_view(request, object_id, form_url,
                                       extra_context)


    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._sincronizar_militares_e_criar_B(obj)
        messages.success(request, "Escala gravada e sincronizada com sucesso.")

    def _sincronizar_militares_e_criar_B(self, escala):
        #Sincroniza EscalaMilitar e cria escala B quando aplicável.
        servico = escala.servico
        tipo_servico = servico.tipo_escalas  # "A", "B", "AB"
        militares_srv = servico.militares.all()

        #  sincronizar militares da escala actual
        EscalaMilitar.objects.filter(escala=escala).exclude(
            militar__in=militares_srv).delete()

        for i, mil in enumerate(militares_srv, 1):
            EscalaMilitar.objects.get_or_create(
                escala=escala,
                militar=mil,
                defaults={"ordem_semana": i, "ordem_fds": i},
            )

        #  se serviço "AB" e esta é A criar/actualizar B
        if tipo_servico == "AB" and not escala.e_escala_b:
            escala_b, _ = Escala.objects.get_or_create(
                servico=servico,
                data=escala.data,
                e_escala_b=True,
                defaults={"comentario": "Gerada automaticamente"},
            )
            EscalaMilitar.objects.filter(escala=escala_b).exclude(
                militar__in=militares_srv).delete()

            for i, mil in enumerate(militares_srv, 1):
                EscalaMilitar.objects.get_or_create(
                    escala=escala_b,
                    militar=mil,
                    defaults={"ordem_semana": i, "ordem_fds": i},
                )

class DispensaAdmin(VersionAdmin):
    list_display = ('militar', 'data_inicio', 'data_fim', 'motivo', 'servico_atual')
    list_filter = ('militar__servicos', 'data_inicio', 'data_fim')
    search_fields = ('militar__nome', 'militar__nim', 'motivo')
    date_hierarchy = 'data_inicio'
    change_list_template = 'admin/core/dispensa/change_list.html'
    
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
            path('adicionar-dispensa/', self.admin_site.admin_view(self.adicionar_dispensa_view), name='adicionar-dispensa'),
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
                'mes': mes,
                'dia_semana': data_atual.strftime('%A'),
                'e_fim_semana': e_fim_semana,
                'e_feriado': e_feriado
            }
            
            dias_por_mes[mes].append(dia_info)
            dias.append(dia_info)
            data_atual += timedelta(days=1)
        
        mapa_dispensas = {}
        for servico in servicos:
            # Obter todos os militares do serviço, ordenados por posto e NIM, usando select_related para otimizar
            militares = servico.militares.all().select_related('user').order_by('posto', 'nim')
            dispensas_servico = {}
            
            # Initialize summary data
            resumo = {
                'dispensados': {},
                'disponiveis': {},
                'total': {}
            }
            
            for militar in militares:
                dispensas = {}
                # Obter todas as dispensas do militar no período
                dispensas_periodo = Dispensa.objects.filter(
                    militar=militar,
                    data_inicio__lte=ultimo_dia_ano,
                    data_fim__gte=hoje
                )
                
                for dia in dias:
                    # Verificar se o militar tem dispensa neste dia
                    dispensa = next(
                        (d for d in dispensas_periodo if d.data_inicio <= dia['data'] <= d.data_fim),
                        None
                    )
                    
                    if dispensa:
                        dispensas[dia['data']] = {
                            'motivo': dispensa.motivo
                        }
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
        
        return render(request, 'admin/mapa_dispensas.html', {
            'mapa_dispensas': mapa_dispensas,
            'dias': dias,
            'dias_por_mes': dias_por_mes,
            'servicos': Servico.objects.filter(ativo=True),
            'servico_selecionado': servico_selecionado,
            'hoje': hoje,
            'dias_restantes': dias_restantes
        })

    def adicionar_dispensa_view(self, request):
        if request.method == 'POST':
            try:
                militar = Militar.objects.get(nim=request.POST.get('militar_nim'))
                dispensa = Dispensa.objects.create(
                    militar=militar,
                    data_inicio=request.POST.get('data_inicio'),
                    data_fim=request.POST.get('data_fim'),
                    motivo=request.POST.get('motivo')
                )
                messages.success(request, 'Dispensa criada com sucesso.')
            except Exception as e:
                messages.error(request, f'Erro ao criar dispensa: {str(e)}')
        
        return redirect('admin:mapa-dispensas')

class FeriadoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'data', 'tipo')
    list_filter = ('tipo',)
    search_fields = ('nome',)
    date_hierarchy = 'data'

class PrevisaoEscalasAdmin(VersionAdmin):
    change_list_template = 'admin/core/escala/previsao.html'

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        
        # Processar geração de previsões
        if request.method == 'POST' and 'gerar_escalas' in request.POST:
            servico_id = request.POST.get('servico')
            data_inicio = request.POST.get('data_inicio')
            data_fim = request.POST.get('data_fim')

            try:
                servico = Servico.objects.get(id=servico_id)
                data_inicio = date.fromisoformat(data_inicio)
                data_fim = date.fromisoformat(data_fim)

                from .utils import gerar_escalas_automaticamente
                if gerar_escalas_automaticamente(servico, data_inicio, data_fim):
                    messages.success(request, "Previsões geradas com sucesso!")
                    # Redirecionar de volta para o mesmo serviço
                    return redirect(f"{request.path}?servico={servico_id}")
                else:
                    messages.error(request, "Erro ao gerar previsões.")
                    # Redirecionar de volta para o mesmo serviço
                    return redirect(f"{request.path}?servico={servico_id}")
            except Exception as e:
                messages.error(request, f"Erro: {str(e)}")
                # Redirecionar de volta para o mesmo serviço
                return redirect(f"{request.path}?servico={servico_id}")

        # Obter serviço selecionado
        servico_id = request.GET.get('servico')
        if servico_id:
            servico = get_object_or_404(Servico, id=servico_id, ativo=True)
        else:
            servico = Servico.objects.filter(ativo=True).first()

        # Obter data de fim da previsão
        data_fim_str = request.GET.get('data_fim')
        if data_fim_str:
            try:
                data_fim = date.fromisoformat(data_fim_str)
            except ValueError:
                data_fim = date.today() + timedelta(days=30)
        else:
            data_fim = date.today() + timedelta(days=30)

        # Preparar contexto
        extra_context.update({
            'servico': servico,
            'servicos': Servico.objects.filter(ativo=True),
            'hoje': date.today(),
            'proximo_mes': date.today().replace(day=1) + timedelta(days=32),
            'data_fim': data_fim,
            'request': request,
        })

        return super().changelist_view(request, extra_context=extra_context)

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
        # Processar geração de previsões
        if request.method == 'POST' and 'gerar_escalas' in request.POST:
            servico_id = request.POST.get('servico')
            data_inicio = request.POST.get('data_inicio')
            data_fim = request.POST.get('data_fim')

            try:
                servico = Servico.objects.get(id=servico_id)
                data_inicio = date.fromisoformat(data_inicio)
                data_fim = date.fromisoformat(data_fim)

                from .utils import gerar_escalas_automaticamente
                if gerar_escalas_automaticamente(servico, data_inicio, data_fim):
                    messages.success(request, "Previsões geradas com sucesso!")
                    # Redirecionar de volta para o mesmo serviço
                    return redirect(f"{request.path}?servico={servico_id}")
                else:
                    messages.error(request, "Erro ao gerar previsões.")
                    # Redirecionar de volta para o mesmo serviço
                    return redirect(f"{request.path}?servico={servico_id}")
            except Exception as e:
                messages.error(request, f"Erro: {str(e)}")
                # Redirecionar de volta para o mesmo serviço
                return redirect(f"{request.path}?servico={servico_id}")

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

        # Calcular próximo mês
        proximo_mes = hoje.replace(day=1) + timedelta(days=32)

        # Obter feriados no período
        feriados = obter_feriados(hoje, data_fim)
        
        # Separar dias por tipo ANTES de processar
        dias_escala = EscalaService.obter_dias_escala(hoje, data_fim)
        
        # Gerar lista de datas com suas escalas
        datas = []
        
        # Processar ESCALA B primeiro (fins de semana/feriados)
        for data in dias_escala['escala_b']:
            # Buscar escala existente para esta data com os militares relacionados
            escala = Escala.objects.filter(
                servico=servico,
                data=data,
                e_escala_b=True
            ).prefetch_related(
                'militares_info',
                'militares_info__militar'
            ).first()

            e_feriado = data in feriados
            datas.append({
                'data': data,
                'escala': escala,
                'e_fim_semana': not e_feriado,
                'e_feriado': e_feriado,
                'tipo_dia': 'feriado' if e_feriado else 'fim_semana'
            })
        
        # Processar ESCALA A depois (dias úteis)
        for data in dias_escala['escala_a']:
            # Buscar escala existente para esta data com os militares relacionados
            escala = Escala.objects.filter(
                servico=servico,
                data=data,
                e_escala_b=False
            ).prefetch_related(
                'militares_info',
                'militares_info__militar'
            ).first()

            datas.append({
                'data': data,
                'escala': escala,
                'e_fim_semana': False,
                'e_feriado': False,
                'tipo_dia': 'util'
            })

        # Ordenar por data
        datas = sorted(datas, key=lambda x: x['data'])

        # Buscar todos os serviços ativos para o seletor
        servicos = Servico.objects.filter(ativo=True)

        context = {
            'title': f'Previsões de Nomeação - {servico.nome}',
            'servico': servico,
            'servicos': servicos,
            'datas': datas,
            'hoje': hoje,
            'data_fim': data_fim,
            'proximo_mes': proximo_mes,
            'opts': self.model._meta,
            'cl': self,
            'is_popup': False,
            'has_add_permission': self.has_add_permission(request),
            'has_change_permission': self.has_change_permission(request),
            'has_delete_permission': self.has_delete_permission(request),
        }

        return render(request, 'admin/core/escala/previsao.html', context)

    class Meta:
        verbose_name = "Previsões de Nomeação"
        verbose_name_plural = "Previsões de Nomeação"

# Proxy model para Previsões de Nomeação
class PrevisaoEscalasProxy(Escala):
    class Meta:
        proxy = True
        verbose_name = "Previsões de Nomeação"
        verbose_name_plural = "Previsões de Nomeação"

# Configuração do Admin Site
class GeradorEscalasAdminSite(admin.AdminSite):
    site_header = 'Gerador de Escalas'
    site_title = 'Gerador de Escalas'
    index_title = 'Administração do Sistema'

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request)
        return app_list

# Criar instância do admin site customizado
admin_site = GeradorEscalasAdminSite(name='admin')
admin_site.register(User, UserAdmin)

# Registrar os modelos no admin site customizado
admin_site.register(Militar, MilitarAdmin)
admin_site.register(Servico, ServicoAdmin)
admin_site.register(Escala, EscalaAdmin)
admin_site.register(Dispensa, DispensaAdmin)
admin_site.register(Feriado, FeriadoAdmin)
admin_site.register(Log)

# Registrar a Previsões de Nomeação como um modelo proxy
admin_site.register(PrevisaoEscalasProxy, PrevisaoEscalasAdmin)


