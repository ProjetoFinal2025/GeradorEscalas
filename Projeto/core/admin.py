from django.shortcuts import render, get_object_or_404, redirect
from reversion.admin import VersionAdmin
from .models import *
from .utils import obter_feriados
from django.utils import timezone
from django.template.defaulttags import register
from .forms import MilitarForm, ServicoForm, EscalaForm
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse, path
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe
from .services.pdf_exports import gerar_pdf_escala
from django.http import FileResponse, Http404, HttpResponse
from collections import defaultdict
from django.contrib import admin, messages
from datetime import date, datetime, timedelta
from django import forms
# Permite alterar os seguintes modelos na admin view
from .models import Militar, Dispensa, Escala, Servico, Log, Feriado, EscalaMilitar, ConfiguracaoUnidade
from .services.escala_service import EscalaService
from django.contrib.admin.models import LogEntry
from django.contrib.admin.views.decorators import staff_member_required
from .views import ERRO_PREVISAO_DIA_ATUAL
from django.db.models import Max
from django.utils.translation import gettext_lazy as _

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@admin.action(description="Limpar nomeações")
def limpar_nomeacoes(modeladmin, request, queryset):
    updated = queryset.update(ultima_nomeacao_a=None, ultima_nomeacao_b=None)
    modeladmin.message_user(request, f"{updated} militares atualizados com sucesso.", messages.SUCCESS)

class MilitarAdmin(VersionAdmin):
    form = MilitarForm
    list_display = ('nome', 'posto_raw', 'nim', 'listar_servicos', 'listar_escalas')
    # Remove a habilidade de mudar o Utilizador de um militar
    readonly_fields = ['user', 'listar_servicos', 'listar_escalas','listar_dispensas']
    actions = [limpar_nomeacoes]

    def posto_raw(self, obj):
        return obj.posto or "(não definido)"
    posto_raw.short_description = "Posto (BD)"

    def get_posto_display(self, obj):
        return obj.get_posto_display()
    get_posto_display.short_description = 'Posto'

class ServicoAdmin(VersionAdmin):
    form = ServicoForm
    list_display = (
        'nome', 'hora_inicio', 'hora_fim', 'n_elementos',
        'n_reservas', 'tipo_escalas', 'armamento',
        'escalas_col',
    )
    list_filter = ('tipo_escalas', 'armamento')
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome',)
        }),
        ('Configurações do Serviço', {
            'fields': ('hora_inicio', 'hora_fim', 'n_elementos', 'n_reservas', 'tipo_escalas', 'armamento'),
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
            qs = obj.escalas.all()
        else:
            qs = Escala.objects.filter(servico=obj)

        # Filtrar conforme o tipo de escalas do serviço
        if obj.tipo_escalas == "A":
            qs = qs.filter(e_escala_b=False)
        elif obj.tipo_escalas == "B":
            qs = qs.filter(e_escala_b=True)
        # Se for "AB" mostra ambas

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
    can_delete = False
    readonly_fields = ("display_militar",)
    fields = ("display_militar", "ordem", "ativo")
    ordering = ("ordem",)
    sortable_by = ("ordem",)
    max_num = 0

    def display_militar(self, obj):
        if not obj.pk:
            return "Selecione acima e salve."
        status = "✅" if obj.ativo else "❌"
        return f"{status} {obj.militar.posto} {obj.militar.nome} ({str(obj.militar.nim).zfill(8)})"

    display_militar.short_description = "Militar"


class EscalaAdmin(VersionAdmin):
    inlines = [EscalaMilitarInline]
    form = EscalaForm

    list_display = ("id", "servico", "tipo_de_escala")
    list_filter = ("servico", "e_escala_b")
    list_display_links = ("id","servico")
    search_fields = ("servico__nome",)
    change_form_template = "admin/escala/militar_escala_change_form.html"

    def tipo_de_escala(self, obj):
        return 'B' if obj.e_escala_b else 'A'

    tipo_de_escala.short_description = 'Tipo de escala'
    tipo_de_escala.admin_order_field = 'e_escala_b'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/export-pdf/",
                self.admin_site.admin_view(self.export_militares_pdf),
                name="core_escala_export_pdf",
            ),
        ]
        return custom_urls + urls

    def export_militares_pdf(self, request, object_id, *args, **kwargs):
        try:
            escala = self.get_object(request, object_id)
            if not escala:
                raise Http404("Escala não encontrada")
            
            pdf_buffer = gerar_pdf_escala(escala)
            if not pdf_buffer:
                raise ValueError("Erro ao gerar o PDF")
            
            filename = f"escala_{escala.pk}_militares.pdf"
            response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            messages.error(request, f"Erro ao gerar PDF: {str(e)}")
            return redirect('admin:core_escala_change', object_id)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            extra_context["export_pdf_url"] = reverse(
                "admin:core_escala_export_pdf",
                args=[object_id],
                current_app=self.admin_site.name
            )
        return super().changeform_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._sincronizar_militares(obj)
        messages.success(request, "Escala gravada e sincronizada com sucesso.")

    @staticmethod
    def _sincronizar_militares(escala):
        militares_srv = list(escala.servico.militares.all())
        existing = EscalaMilitar.objects.filter(escala=escala).select_related("militar")
        existing_by_mil = {em.militar_id: em for em in existing}

        # apagar designações órfãs
        (
            EscalaMilitar.objects
            .filter(escala=escala)
            .exclude(militar__in=militares_srv)
            .delete()
        )

        # Obter a maior ordem existente
        max_ordem = existing.aggregate(Max('ordem'))['ordem__max'] or 0

        # Adicionar apenas os novos militares ao final, preservando a ordem dos existentes
        for mil in militares_srv:
            if mil.pk not in existing_by_mil:
                max_ordem += 1
                EscalaMilitar.objects.create(
                    escala=escala,
                    militar=mil,
                    ordem=max_ordem
                )

class DispensaAdmin(VersionAdmin):
    list_display = ('militar', 'data_inicio', 'data_fim', 'motivo', 'servico_atual')
    list_filter = ('militar__servicos', 'data_inicio', 'data_fim')
    search_fields = ('militar__nome', 'militar__nim', 'motivo')
    date_hierarchy = 'data_inicio'
    change_list_template = 'admin/dispensa/change_list.html'
    
    def servico_atual(self, obj):
        servicos = obj.militar.servicos.all()
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
        servicos = Servico.objects.all()
        
        if servico_id:
            servico_selecionado = get_object_or_404(Servico, id=servico_id)
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
        
        if dias:
            feriados = obter_feriados(min(d['data'] for d in dias), max(d['data'] for d in dias))
        else:
            feriados = []

        return render(request, 'admin/mapa_dispensas.html', {
            'mapa_dispensas': mapa_dispensas,
            'dias': dias,
            'dias_por_mes': dias_por_mes,
            'servicos': Servico.objects.all(),
            'servico_selecionado': servico_selecionado,
            'hoje': hoje,
            'dias_restantes': dias_restantes,
            'feriados': feriados,
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
    """
    Tela de previsões de nomeação:
    gera escalas, mostra dias futuros, permite remover flag 'prevista'.
    """
    change_list_template = 'admin/escala/previsao.html'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    # Página padrão (changelist) ‒ só injeta contexto extra

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['ERRO_PREVISAO_DIA_ATUAL'] = ERRO_PREVISAO_DIA_ATUAL

        # processar POST de geração rápida
        if request.method == "POST" and "gerar_escalas" in request.POST:
            servico_id = request.POST.get("servico")
            data_inicio = request.POST.get("data_inicio")
            data_fim = request.POST.get("data_fim")

            try:
                servico = Servico.objects.get(pk=servico_id)
                data_inicio = date.fromisoformat(data_inicio)
                data_fim = date.fromisoformat(data_fim)

                # Verificar se há escassez de militares e emitir um aviso prévio
                alerta = EscalaService.gerar_alerta_escassez_militares(servico, data_inicio, data_fim)
                if alerta:
                    messages.warning(request, alerta)

                ok = EscalaService.gerar_escalas_automaticamente(servico, data_inicio, data_fim)
                if not ok and data_inicio <= date.today():
                    messages.error(request, ERRO_PREVISAO_DIA_ATUAL)
                else:
                    msg = "Previsões geradas com sucesso!" if ok else "Erro ao gerar previsões."
                    (messages.success if ok else messages.error)(request, msg)

            except Exception as exc:  # pylint: disable=broad-except
                messages.error(request, f"Erro: {exc}")

            # redireciona sempre para a mesma página (GET)
            return redirect(f"{request.path}?servico={servico_id}")

        # serviço activo seleccionado
        servico_id = request.GET.get("servico")
        servicos = Servico.objects.all()

        if not servicos.exists():
            messages.warning(request, "Não há serviços no sistema. Por favor, ative um serviço primeiro.")
            return redirect("admin:core_servico_changelist")

        servico = (
            servicos.get(pk=servico_id)
            if servico_id
            else servicos.first()
        )

        data_fim_str = request.GET.get("data_fim")
        try:
            data_fim = date.fromisoformat(data_fim_str) if data_fim_str else None
        except ValueError:
            data_fim = None
        data_fim = data_fim or date.today() + timedelta(days=30)

        extra_context.update(
            {
                "servico": servico,
                "servicos": Servico.objects.all(),
                "hoje": date.today(),
                "proximo_mes": date.today().replace(day=1) + timedelta(days=32),
                "data_fim": data_fim,
                "request": request,
            }
        )
        return super().changelist_view(request, extra_context=extra_context)


    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "",
                self.admin_site.admin_view(self.previsao_view),
                name="core_previsaoescalasproxy_changelist",
            ),
            path(
                "remover-previsao/<int:escala_id>/",
                self.admin_site.admin_view(self.remover_previsao),
                name="remover_previsao",
            ),
        ]
        return custom + urls

    #  Remover flag 'prevista' de uma Escala
    def remover_previsao(self, request, escala_id):
        try:
            escala = Escala.objects.get(pk=escala_id)
        except Escala.DoesNotExist:
            messages.error(request, "Escala não encontrada.")
            return redirect("admin:core_previsaoescalasproxy_changelist")

        if not escala.prevista:
            messages.warning(request, "Esta nomeação já não é uma previsão.")
            return redirect("admin:core_previsaoescalasproxy_changelist")

        escala.prevista = False
        escala.save()
        messages.success(request, "Status de previsão removido com sucesso.")

        hoje = date.today()
        proxima = (
            Nomeacao.objects.filter(
                escala_militar__escala__servico=escala.servico,
                escala_militar__escala__prevista=True,
                data__gt=hoje,
            )
            .order_by("data")
            .first()
        )
        proxima_data = proxima.data if proxima else hoje

        url = (
            f"{reverse('admin:core_previsaoescalasproxy_changelist')}"
            f"?servico={escala.servico.pk}&data_inicio={proxima_data.isoformat()}"
        )
        if "data_fim" in request.GET:
            url += f"&data_fim={request.GET['data_fim']}"
        return redirect(url)

    # 5. Tela principal de previsões

    def previsao_view(self, request):
        # ---------- geração automática (POST) ----------
        if request.method == "POST" and "gerar_escalas" in request.POST:
            servico_id = request.POST.get("servico")
            data_inicio = date.fromisoformat(request.POST.get("data_inicio"))
            data_fim = date.fromisoformat(request.POST.get("data_fim"))
            servico = Servico.objects.get(pk=servico_id)

            # Se o utilizador não confirmou, verificar a escassez
            if "confirmar_geracao" not in request.POST:
                periodos_alerta = EscalaService.gerar_alerta_escassez_militares(servico, data_inicio, data_fim)
                if periodos_alerta:
                    # Se houver escassez, renderizar novamente a página com dados para o modal
                    context = self.get_previsao_context(request, servico, data_fim)
                    context.update({
                        'alerta_escassez_periodos': periodos_alerta,
                        'form_data_POST': request.POST, # Para reenviar os dados
                    })
                    return render(request, 'admin/escala/previsao.html', context)

            # Se não houve alerta ou o utilizador confirmou, gerar a escala
            ok = EscalaService.gerar_escalas_automaticamente(servico, data_inicio, data_fim)
            if ok:
                messages.success(request, "Previsões geradas com sucesso!")
            else:
                messages.error(request, "Ocorreu um erro ao gerar as previsões.")

            return redirect(f"{request.path}?servico={servico_id}&data_fim={data_fim.isoformat()}")

        # ---------- parâmetros GET ----------
        servico_id = request.GET.get("servico")
        servicos = Servico.objects.all()

        if not servicos.exists():
            messages.warning(request, "Não há serviços no sistema. Por favor, ative um serviço primeiro.")
            return redirect("admin:core_servico_changelist")

        servico = (
            servicos.get(pk=servico_id)
            if servico_id
            else servicos.first()
        )

        hoje = date.today()
        try:
            data_fim = date.fromisoformat(request.GET.get("data_fim", ""))
        except (ValueError, TypeError):
            data_fim = hoje + timedelta(days=30)
        
        context = self.get_previsao_context(request, servico, data_fim)
        return render(request, 'admin/escala/previsao.html', context)

    def get_previsao_context(self, request, servico, data_fim):
        """Método auxiliar para construir o contexto da página de previsão."""
        hoje = date.today()
        # ---------- feriados / dias de escala ----------
        feriados = obter_feriados(hoje, data_fim)
        dias_escala = EscalaService.obter_dias_escala(hoje, data_fim)

        datas = []

        # --- histórico (últimos 30 dias) ---
        historico_ini = hoje - timedelta(days=30)
        historico_qs = (
            Nomeacao.objects.filter(
                escala_militar__escala__servico=servico,
                data__gte=historico_ini,
                data__lte=hoje,
            )
            .select_related("escala_militar__escala", "escala_militar__militar")
            .order_by("data")
        )

        nomeacoes_por_dia = defaultdict(list)
        for nomeacao in historico_qs:
            nomeacoes_por_dia[nomeacao.data].append(nomeacao)

        # Adicionar histórico aos dados
        for dia, nomeacoes in nomeacoes_por_dia.items():
            e_feriado = dia in feriados
            e_fim_semana = dia.weekday() >= 5
            datas.append({
                "data": dia, "nomeacoes": nomeacoes, "e_fim_semana": e_fim_semana and not e_feriado,
                "e_feriado": e_feriado, "tipo_dia": "feriado" if e_feriado else ("fim_semana" if e_fim_semana else "util")
            })

        # --- futuros | Escala B (fds / feriados) ---
        for dia in dias_escala.get("escala_b", []):
            if dia <= hoje and any(d["data"] == dia for d in datas):
                continue
            escala = Escala.objects.filter(
                servico=servico,
                e_escala_b=True
            ).first()
            nomeacoes = []
            if escala:
                nomeacoes = Nomeacao.objects.filter(
                    escala_militar__escala=escala,
                    data=dia
                ).select_related("escala_militar__militar")

            e_feriado = dia in feriados
            datas.append(
                {
                    "data": dia,
                    "escala": escala,
                    "nomeacoes": nomeacoes,
                    "e_fim_semana": not e_feriado,
                    "e_feriado": e_feriado,
                    "tipo_dia": "fim_semana" if not e_feriado else "feriado",
                }
            )

        # --- futuros | Escala A (dias úteis) ---
        for dia in dias_escala.get("escala_a", []):
            if dia <= hoje and any(d["data"] == dia for d in datas):
                continue
            escala = Escala.objects.filter(
                servico=servico,
                e_escala_b=False
            ).first()
            nomeacoes = []
            if escala:
                nomeacoes = Nomeacao.objects.filter(
                    escala_militar__escala=escala,
                    data=dia
                ).select_related("escala_militar__militar")

            datas.append(
                {
                    "data": dia,
                    "escala": escala,
                    "nomeacoes": nomeacoes,
                    "e_fim_semana": False,
                    "e_feriado": False,
                    "tipo_dia": "util",
                }
            )

        # ordena a lista consolidada
        datas.sort(key=lambda x: x["data"])

        # ---------- render ----------
        context = {
            "title": f"Previsões de Nomeação – {servico.nome}",
            "servico": servico,
            "servicos": Servico.objects.all(),
            "datas": datas,
            "hoje": hoje,
            "data_fim": data_fim,
            "proximo_mes": hoje.replace(day=1) + timedelta(days=32),
            "opts": self.model._meta,
            "cl": self,
            "is_popup": False,
            "has_add_permission": self.has_add_permission(request),
            "has_change_permission": self.has_change_permission(request),
            "has_delete_permission": self.has_delete_permission(request),
        }
        return context

    class Meta:
        verbose_name = "Previsões de Nomeação"
        verbose_name_plural = "Previsões de Nomeação"


# Proxy model para Previsões de Nomeação
class PrevisaoEscalasProxy(Escala):
    class Meta:
        proxy = True
        verbose_name = "Previsões de Nomeação"
        verbose_name_plural = "Previsões de Nomeação"

class ConfiguracaoUnidadeAdmin(VersionAdmin):
    list_display = ('nome_unidade', 'nome_subunidade')
    fieldsets = (
        ('Configuração da Unidade', {
            'fields': ('nome_unidade', 'nome_subunidade'),
            'description': 'Configure o nome da unidade e da subunidade que aparecerão nos documentos exportados.'
        }),
    )

class LogAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

# Configuração do Admin Site
class GeradorEscalasAdminSite(admin.AdminSite):
    site_header = 'Gerador de Escalas'
    site_title = 'Gerador de Escalas'
    index_title = 'Administração do Sistema'

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)
        for app in app_list:
            if app['app_label'] == 'core':
                # Adiciona o link customizado no fim da lista de modelos
                app['models'].append({
                    'name': 'Lista de Serviços',
                    'object_name': 'ListaServicos',
                    'admin_url': '/servicos/',  # URL absoluto para a view
                    'add_url': None,
                    'view_only': True,
                })
                # Ordenar modelos, colocando 'Previsões de Nomeação' no fim
                app['models'].sort(key=lambda m: m['name'] == 'Previsões de Nomeação')
                # Ordenar modelos, colocando 'Lista de Serviços' no fim
                app['models'].sort(key=lambda m: m['name'] == 'Lista de Serviços')
                # Ordenar explicitamente os modelos conforme a ordem desejada
                ordem = [
                    'Configuração da Unidade',
                    'Feriados',
                    'Militares',
                    'Dispensas',
                    'Servicos',
                    'Escalas',
                    'Previsões de Nomeação',
                    'Lista de Serviços',
                    'Logs',
                ]
                def key_ordem(m):
                    try:
                        return ordem.index(m['name'])
                    except ValueError:
                        return 100  # Fica no fim se não estiver na lista
                app['models'].sort(key=key_ordem)
        return app_list

    def index(self, request, extra_context=None):
        from .models import Servico, Militar, Dispensa, Nomeacao, EscalaMilitar
        from django.db.models import Count
        extra_context = extra_context or {}

        # Serviços
        servicos = Servico.objects.all()
        extra_context['servicos'] = servicos

        # Militares por serviço
        militares_por_servico = {s.nome: s.militares.count() for s in servicos}
        extra_context['militares_por_servico'] = militares_por_servico
        total_militares = sum(militares_por_servico.values())
        extra_context['total_militares'] = total_militares

        # Militares dispensados por serviço (atuais)
        hoje = timezone.now().date()
        dispensados_por_servico = {}
        for servico in servicos:
            militares = servico.militares.all()
            count = militares.filter(
                dispensas__data_inicio__lte=hoje,
                dispensas__data_fim__gte=hoje
            ).distinct().count()
            dispensados_por_servico[servico.nome] = count
        extra_context['dispensados_por_servico'] = dispensados_por_servico

        # Top 5 militares com mais serviços realizados (nome + posto)
        top_militares_qs = (
            Nomeacao.objects
            .values('escala_militar__militar__nome', 'escala_militar__militar__posto')
            .annotate(total=Count('id'))
            .order_by('-total')[:5]
        )
        top_militares = [
            (f"{item['escala_militar__militar__posto']} {item['escala_militar__militar__nome']}", item['total'])
            for item in top_militares_qs
        ]
        extra_context['top_militares'] = top_militares

        # Militares sem escala
        todos_nims = set(Militar.objects.values_list('nim', flat=True))
        nims_com_escala = set(EscalaMilitar.objects.values_list('militar__nim', flat=True))
        total_sem_escala = len(todos_nims - nims_com_escala)
        extra_context['total_militares_sem_escala'] = total_sem_escala

        # Adicionar ações recentes ao contexto (últimas 10 ações do utilizador)
        recent_actions = (
            LogEntry.objects.filter(user=request.user)
            .select_related("content_type")
            .order_by("-action_time")[:10]
        )
        extra_context['recent_actions'] = recent_actions

        return super().index(request, extra_context=extra_context)

# Criar instância do admin site customizado
admin_site = GeradorEscalasAdminSite(name='admin')
admin_site.register(User, UserAdmin)

# Registrar os modelos no admin site customizado
admin_site.register(Militar, MilitarAdmin)
admin_site.register(Servico, ServicoAdmin)
admin_site.register(Escala, EscalaAdmin)
admin_site.register(Dispensa, DispensaAdmin)
admin_site.register(Feriado, FeriadoAdmin)
admin_site.register(PrevisaoEscalasProxy, PrevisaoEscalasAdmin)
admin_site.register(ConfiguracaoUnidade, ConfiguracaoUnidadeAdmin)
admin_site.register(Log, LogAdmin)
# Registrar a Previsões de Nomeação como um modelo proxy (no fim)


