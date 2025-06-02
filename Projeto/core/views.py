from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from datetime import datetime, timedelta, date
from .models import Servico, Dispensa, Escala, Militar, EscalaMilitar, Nomeacao, ConfiguracaoUnidade
from .forms import *
from .services.escala_service import EscalaService
from .utils import obter_feriados
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.admin.models import LogEntry
from django.db.models import Count
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import cm
import json
from django.views.generic import TemplateView
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt


# Mensagens de erro constantes
ERRO_PREVISAO_DIA_ATUAL = "Não é permitido gerar previsões para o dia de hoje. Por favor, escolha uma data futura."

# view de log in
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']  # normalmente o nim
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            # Redireta Para o dashboard necessário
            if user.is_staff:
                return redirect('/admin/')
            else:
                return redirect('home')
        else:
            messages.error(request, 'NIM ou senha inválidos.')

    return render(request, 'login.html')

from django.http import HttpResponse

## Testar se log in foi executado
@login_required
def home_view(request):
    # Serviços
    servicos = Servico.objects.all()
    militares_por_servico = {s.nome: s.militares.count() for s in servicos}
    total_militares = sum(militares_por_servico.values())

    hoje = date.today()
    amanha = hoje + timedelta(days=1)
    dispensas_ativas = Dispensa.objects.filter(data_inicio__lte=hoje, data_fim__gte=hoje)
    total_dispensados = dispensas_ativas.values('militar').distinct().count()

    # Top 5 militares com mais serviços realizados
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

    # Calcular dispensados hoje e nomeados para hoje/amanhã por serviço
    servicos_info = []
    for servico in servicos:
        # Dispensados hoje neste serviço
        dispensados_hoje = Dispensa.objects.filter(
            militar__servicos=servico,
            data_inicio__lte=hoje,
            data_fim__gte=hoje
        ).values('militar').distinct().count()
        # Nomeado para hoje
        nomeacao_hoje = Nomeacao.objects.filter(
            escala_militar__escala__servico=servico,
            data=hoje,
            e_reserva=False
        ).select_related('escala_militar__militar').first()
        militar_hoje = nomeacao_hoje.escala_militar.militar if nomeacao_hoje else None
        # Nomeado para amanhã
        nomeacao_amanha = Nomeacao.objects.filter(
            escala_militar__escala__servico=servico,
            data=amanha,
            e_reserva=False
        ).select_related('escala_militar__militar').first()
        militar_amanha = nomeacao_amanha.escala_militar.militar if nomeacao_amanha else None
        # Cor do banner conforme regras fornecidas
        nome_lower = servico.nome.lower()
        if "oficial" in nome_lower:
            cor_banner = "bg-danger text-white"  # vermelho
        elif "sargento" in nome_lower or "comandante" in nome_lower:
            cor_banner = "bg-success text-white"  # verde
        elif "cabo" in nome_lower:
            cor_banner = "bg-primary text-white"  # azul
        elif "graduado" in nome_lower:
            cor_banner = "bg-secondary text-white"  # roxo/cinzento
        else:
            cor_banner = "bg-warning text-dark"  # amarelo (praças)
        servicos_info.append({
            'obj': servico,
            'total_militares': militares_por_servico.get(servico.nome, 0),
            'dispensados_hoje': dispensados_hoje,
            'militar_hoje': militar_hoje,
            'militar_amanha': militar_amanha,
            'cor_banner': cor_banner,
        })

    context = {
        'servicos_info': servicos_info,
        'total_militares': total_militares,
        'total_dispensados': total_dispensados,
        'top_militares': top_militares,
        'hoje': hoje,
    }
    return render(request, 'core/home.html', context)

@login_required
def mapa_dispensas_view(request):
    # Obter o serviço selecionado do filtro
    servico_id = request.GET.get('servico')
    servico_selecionado = None
    servicos = Servico.objects.all()
    
    if servico_id:
        servico_selecionado = get_object_or_404(Servico, id=servico_id)
        servicos = [servico_selecionado]
    
    hoje = date.today()
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
        militares = servico.militares.all().select_related('user').order_by('posto', 'nim')
        dispensas_servico = {}
        resumo = {
            'dispensados': {},
            'disponiveis': {},
            'total': {}
        }
        for militar in militares:
            dispensas = {}
            dispensas_periodo = Dispensa.objects.filter(
                militar=militar,
                data_inicio__lte=ultimo_dia_ano,
        data_fim__gte=hoje
            )
            for dia in dias:
                dispensa = next(
                    (d for d in dispensas_periodo if d.data_inicio <= dia['data'] <= d.data_fim),
                    None
                )
                if dispensa:
                    dispensas[dia['data']] = {
                        'motivo': dispensa.motivo
                    }
                    if dia['data'] not in resumo['dispensados']:
                        resumo['dispensados'][dia['data']] = 0
                    resumo['dispensados'][dia['data']] += 1
                if dia['data'] not in resumo['total']:
                    resumo['total'][dia['data']] = 0
                resumo['total'][dia['data']] += 1
            dispensas_servico[militar] = dispensas
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
    context = {
        'mapa_dispensas': mapa_dispensas,
        'dias': dias,
        'dias_por_mes': dias_por_mes,
        'servicos': Servico.objects.all(),
        'servico_selecionado': servico_selecionado,
        'hoje': hoje,
        'dias_restantes': dias_restantes,
        'feriados': feriados,
    }
    return render(request, 'core/mapa_dispensas_publica.html', context)

@login_required
def escala_servico_view(request, servico_id):
    servico = get_object_or_404(Servico, id=servico_id)
    escala_service = EscalaService()
    
    # Obter data inicial e final
    hoje = date.today()
    data_fim = hoje + timedelta(days=30)
    
    # Obter escalas do período
    escalas = Escala.objects.filter(
        servico=servico,
    ).order_by('id')
    
    # Obter feriados
    feriados = obter_feriados(hoje, data_fim)
    
    context = {
        'servico': servico,
        'escalas': escalas,
        'feriados': feriados,
        'hoje': hoje,
        'data_fim': data_fim
    }
    
    return render(request, 'core/escala_servico.html', context)

@login_required
def gerar_escalas_view(request, servico_id):
    servico = get_object_or_404(Servico, id=servico_id)
    escala_service = EscalaService()
    
    if request.method == 'POST':
        data_inicio = request.POST.get('data_inicio')
        data_fim = request.POST.get('data_fim')
        
        try:
            data_inicio = date.fromisoformat(data_inicio)
            data_fim = date.fromisoformat(data_fim)
            
            # Gerar previsões
            previsoes = escala_service.gerar_previsao(servico, data_inicio, data_fim)
            
            if previsoes:
                messages.success(request, "Previsões geradas com sucesso!")
            else:
                messages.error(request, "Erro ao gerar previsões.")
                
        except Exception as e:
            messages.error(request, f"Erro: {str(e)}")
            
        return redirect('escala_servico', servico_id=servico_id)
    
    # Obter data inicial e final
    hoje = date.today()
    data_fim = hoje + timedelta(days=30)
    
    context = {
        'servico': servico,
        'hoje': hoje,
        'data_fim': data_fim
    }
    
    return render(request, 'core/gerar_escalas.html', context)


guia_view = staff_member_required(
    TemplateView.as_view(template_name='admin/guia.html')
)


@staff_member_required
def nomear_militares_view(request):
    servicos = Servico.objects.all()
    servico = None
    data = None
    militares_disponiveis = []
    
    if request.method == 'GET':
        servico_id = request.GET.get('servico')
        data_str = request.GET.get('data')
        
        if servico_id:
            servico = Servico.objects.get(id=servico_id)
            if data_str:
                try:
                    data = datetime.strptime(data_str, '%Y-%m-%d').date()
                    nomeacao_service = NomeacaoService()
                    militares_disponiveis = nomeacao_service.obter_militares_disponiveis(data)
                except ValueError:
                    pass
    
    elif request.method == 'POST':
        servico_id = request.GET.get('servico')
        data_str = request.GET.get('data')
        militar_id = request.POST.get('militar_id')
        posicao = request.POST.get('posicao')
        
        if servico_id and data_str and militar_id and posicao:
            try:
                servico = Servico.objects.get(id=servico_id)
                data = datetime.strptime(data_str, '%Y-%m-%d').date()
                militar = Militar.objects.get(nim=militar_id)
                
                nomeacao_service = NomeacaoService()
                nomeacao_service.criar_nomeacao(militar, servico, data, posicao)
                
                return redirect('nomear_militares')
            except (Servico.DoesNotExist, Militar.DoesNotExist, ValueError):
                pass
    
    context = {
        'servicos': servicos,
        'servico': servico,
        'data': data,
        'militares_disponiveis': militares_disponiveis,
    }
    
    return render(request, 'admin/core/escala/nomear_militares.html', context)

@login_required
def nomear_militares(request, escala_id):
    escala = get_object_or_404(Escala, pk=escala_id)
    escala_service = EscalaService()

    # --------- determinar a data em que vamos nomear ----------
    # • primeiro tenta vir no GET ?data=AAAA-MM-DD
    # • se vier em POST (hidden input), também funciona
    data_str = request.GET.get("data") or request.POST.get("data")
    data_ref = parse_date(data_str) if data_str else None
    if data_ref is None:
        messages.error(request, "Data da escala não informada.")
        return redirect('escala_servico', servico_id=escala.servico.pk)

    # --------- ações POST ----------
    if request.method == "POST":
        try:
            escala_service.aplicar_previsao([escala], data_ref)
            messages.success(request, "Militares nomeados com sucesso!")
        except Exception as exc:
            messages.error(request, f"Erro: {exc}")
        return redirect('escala_servico', servico_id=escala.servico.pk)

    # --------- GET: mostrar tela ----------
    militares = escala_service.obter_militares_disponiveis(
        escala.servico,
        data_ref,
    )

    context = {
        "escala":    escala,
        "data_ref":  data_ref,
        "militares": militares,
    }
    return render(request, "core/nomear_militares.html", context)

@login_required
def lista_servicos_view(request):
    servicos = list(Servico.objects.all())
    hoje = date.today()
    
    # Obter o índice inicial dos serviços a mostrar
    pagina = int(request.GET.get('pagina', 1))
    servicos_por_pagina = 2
    total_paginas = (len(servicos) + servicos_por_pagina - 1) // servicos_por_pagina
    pagina = min(max(1, pagina), total_paginas)
    inicio = (pagina - 1) * servicos_por_pagina
    servicos_paginados = servicos[inicio:inicio + servicos_por_pagina]
    
    # Obter todas as nomeações a partir de hoje
    nomeacoes = Nomeacao.objects.filter(data__gte=hoje).select_related('escala_militar__escala', 'escala_militar__militar')
    datas_raw = sorted(set(n.data for n in nomeacoes))
    
    # Obter feriados para o intervalo das datas
    if datas_raw:
        feriados = obter_feriados(min(datas_raw), max(datas_raw))
        feriados_set = set(feriados)
    else:
        feriados = []
        feriados_set = set()
    
    # Construir estrutura: lista de dicts com data e tipo_dia
    datas = []
    for d in datas_raw:
        if d in feriados_set:
            tipo_dia = 'feriado'
        elif d.weekday() >= 5:
            tipo_dia = 'fim_semana'
        else:
            tipo_dia = 'util'
        datas.append({'data': d, 'tipo_dia': tipo_dia})
    
    # Construir tabela: {data: {servico: {'efetivo': [], 'reserva': []}}}
    tabela = {}
    for d in datas_raw:
        tabela[d] = {}
        for servico in servicos_paginados:
            tabela[d][servico.id] = {'efetivo': [], 'reserva': []}
    
    for n in nomeacoes:
        servico_id = n.escala_militar.escala.servico_id
        if servico_id in [s.id for s in servicos_paginados]:
            if n.e_reserva:
                tabela[n.data][servico_id]['reserva'].append(n.escala_militar.militar)
            else:
                tabela[n.data][servico_id]['efetivo'].append(n.escala_militar.militar)
    
    return render(request, 'core/lista_servicos.html', {
        'servicos': servicos_paginados,
        'datas': datas,
        'tabela': tabela,
        'pagina_atual': pagina,
        'total_paginas': total_paginas,
    })

@login_required
def previsoes_por_servico_view(request):
    servicos = Servico.objects.all()
    if request.method == 'POST':
        servico_id = request.POST.get('servico_id')
        if servico_id:
            return redirect('previsoes_servico', servico_id=servico_id)
    return render(request, 'core/previsoes_por_servico.html', {'servicos': servicos})

@login_required
def previsoes_servico_view(request, servico_id):
    servico = get_object_or_404(Servico, id=servico_id)
    hoje = date.today()
    nomeacoes = Nomeacao.objects.filter(
        escala_militar__escala__servico=servico,
        data__gte=hoje
    ).select_related('escala_militar__militar', 'escala_militar__escala').order_by('data')

    nomeacoes_por_data = {}
    observacoes_por_data = {}
    datas_set = set(n.data for n in nomeacoes)
    for n in nomeacoes:
        nomeacoes_por_data.setdefault(n.data, {'efetivos': [], 'reservas': []})
        militar_obj = n.escala_militar.militar
        if militar_obj:
            militar_str = f"{militar_obj.posto} {militar_obj.nome} {militar_obj.nim}"
        else:
            militar_str = "N/A"
        if n.e_reserva:
            nomeacoes_por_data[n.data]['reservas'].append(militar_str)
        else:
            nomeacoes_por_data[n.data]['efetivos'].append(militar_str)
        # Juntar observações das nomeações do dia
        if n.data not in observacoes_por_data:
            observacoes_por_data[n.data] = set()
        if n.observacoes:
            observacoes_por_data[n.data].add(n.observacoes)

    # Junta as observações em string
    observacoes_por_data = {k: ' | '.join(v) for k, v in observacoes_por_data.items()}

    # Identificar feriados e fins de semana
    if datas_set:
        feriados = set(obter_feriados(min(datas_set), max(datas_set)))
    else:
        feriados = set()
    dias = []
    for d in sorted(datas_set):
        if d in feriados:
            tipo_dia = 'feriado'
        elif d.weekday() >= 5:
            tipo_dia = 'fim_semana'
        else:
            tipo_dia = 'util'
        dias.append({'data': d, 'tipo_dia': tipo_dia})

    return render(request, 'core/previsoes_servico.html', {
        'servico': servico,
        'dias': dias,
        'nomeacoes_por_data': nomeacoes_por_data,
        'observacoes_por_data': observacoes_por_data,
    })

@login_required
def previsualizar_previsoes_pdf(request, servico_id):
    """Pré-visualiza o PDF das previsões no navegador."""
    response = exportar_previsoes_pdf(request, servico_id, download=False)
    return response

@login_required
def exportar_previsoes_pdf(request, servico_id, download=True):
    servico = get_object_or_404(Servico, id=servico_id)
    hoje = date.today()
    nomeacoes = Nomeacao.objects.filter(
        escala_militar__escala__servico=servico,
        data__gte=hoje
    ).select_related('escala_militar__militar', 'escala_militar__escala').order_by('data')

    if not nomeacoes.exists():
        messages.error(request, "Não existem nomeações para exportar.")
        return redirect('previsoes_servico', servico_id=servico_id)

    data_inicio = nomeacoes.first().data
    data_fim = nomeacoes.last().data
    feriados = obter_feriados(data_inicio, data_fim)
    feriados_set = set(feriados)
    # Gerar lista de dias exatamente como na grelha de previsões
    datas_set = set(n.data for n in nomeacoes)
    if datas_set:
        feriados = set(obter_feriados(min(datas_set), max(datas_set)))
    else:
        feriados = set()
    dias = []
    for d in sorted(datas_set):
        if d in feriados:
            tipo_dia = 'feriado'
        elif d.weekday() >= 5:
            tipo_dia = 'fim_semana'
        else:
            tipo_dia = 'util'
        dias.append({'data': d, 'tipo_dia': tipo_dia})
    nomeacoes_por_data = {}
    observacoes_por_data = {}
    for n in nomeacoes:
        nomeacoes_por_data.setdefault(n.data, {'efetivo': None, 'reserva': None})
        if n.e_reserva:
            nomeacoes_por_data[n.data]['reserva'] = n.escala_militar.militar
        else:
            nomeacoes_por_data[n.data]['efetivo'] = n.escala_militar.militar
        observacoes_por_data[n.data] = n.escala_militar.escala.observacoes if n.escala_militar.escala else ''

    # Obter nome da unidade e subunidade
    config = ConfiguracaoUnidade.objects.first()
    if config:
        if config.nome_subunidade:
            nome_cabecalho = f"{config.nome_unidade} - {config.nome_subunidade}"
        else:
            nome_cabecalho = config.nome_unidade
    else:
        nome_cabecalho = "Unidade Militar"

    response = HttpResponse(content_type='application/pdf')
    if download:
        response['Content-Disposition'] = f'attachment; filename="previsoes_{servico.nome}.pdf"'
    else:
        response['Content-Disposition'] = f'inline; filename="previsoes_{servico.nome}.pdf"'
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    timestamp = datetime.now().strftime('Exportado em: %d/%m/%Y %H:%M')

    def draw_header():
        # Centralizar o nome da unidade
        p.setFont("Helvetica-Bold", 16)
        text_width = p.stringWidth(nome_cabecalho, "Helvetica-Bold", 16)
        x_centro = (width - text_width) / 2
        p.drawString(x_centro, height-2*cm, nome_cabecalho)
        
        p.setFont("Helvetica-Bold", 14)
        p.drawString(2*cm, height-3*cm, f"Previsões de Nomeação – {servico.nome}")
        # Adicionar timestamp no canto superior direito
        p.setFont("Helvetica", 8)
        p.drawRightString(width-2*cm, height-1.5*cm, timestamp)
        p.setFont("Helvetica", 10)

    def draw_footer():
        p.setFont("Helvetica", 8)
        # Desenhar o aviso mais abaixo
        aviso = "Atenção: Estas previsões podem ser alteradas. Deve sempre consultar a Ordem de Serviço antes de sair da Unidade."
        p.drawString(2*cm, 1*cm, aviso)

    draw_header()
    draw_footer()
    y = height-4*cm

    # Cabeçalho da tabela
    p.setFillColor(colors.HexColor('#4A5D23'))
    p.rect(2*cm, y, width-4*cm, 0.7*cm, fill=1)
    p.setFillColor(colors.white)
    p.drawString(2.1*cm, y+0.2*cm, "Data")
    p.drawString(5*cm, y+0.2*cm, "Efetivo")
    p.drawString(10*cm, y+0.2*cm, "Reserva")
    p.drawString(15*cm, y+0.2*cm, "Observações")
    y -= 0.7*cm

    for dia in dias:
        if y < 2*cm:
            p.showPage()
            draw_header()
            draw_footer()
            y = height-3*cm
            p.setFont("Helvetica", 10)
            y -= 1*cm
            p.setFillColor(colors.HexColor('#4A5D23'))
            p.rect(2*cm, y, width-4*cm, 0.7*cm, fill=1)
            p.setFillColor(colors.white)
            p.drawString(2.1*cm, y+0.2*cm, "Data")
            p.drawString(5*cm, y+0.2*cm, "Efetivo")
            p.drawString(10*cm, y+0.2*cm, "Reserva")
            p.drawString(15*cm, y+0.2*cm, "Observações")
            y -= 0.7*cm

        data_str = dia['data'].strftime('%d/%m/%Y')
        nomeacoes = nomeacoes_por_data.get(dia['data'], {})
        efetivo = nomeacoes.get('efetivo')
        reserva = nomeacoes.get('reserva')
        obs = observacoes_por_data.get(dia['data'], '')

        # Destacar Escala B (fim de semana ou feriado)
        if dia['tipo_dia'] in ['feriado', 'fim_semana']:
            p.saveState()
            p.setFillColor(colors.HexColor('#e6f2d8'))
            p.rect(2*cm, y, width-4*cm, 0.6*cm, fill=1, stroke=0)
            p.restoreState()
            p.setFont("Helvetica-Bold", 9)
            p.setFillColor(colors.HexColor('#4A5D23'))
        else:
            p.setFont("Helvetica", 9)
            p.setFillColor(colors.black)

        p.drawString(2.1*cm, y+0.1*cm, data_str)
        p.drawString(5*cm, y+0.1*cm, f"{efetivo.posto} {efetivo.nome}" if efetivo else "—")
        p.drawString(10*cm, y+0.1*cm, f"{reserva.posto} {reserva.nome}" if reserva else "—")
        p.drawString(15*cm, y+0.1*cm, obs[:40])
        y -= 0.6*cm

    p.showPage()
    p.save()
    return response

@login_required
def exportar_escalas_pdf(request, servico_id):
    servico = get_object_or_404(Servico, id=servico_id)
    hoje = date.today()
    data_fim = hoje + timedelta(days=30)
    escalas = Escala.objects.filter(servico=servico).prefetch_related('militares_info__militar').order_by('id')
    
    # Obter nome da unidade e subunidade
    config = ConfiguracaoUnidade.objects.first()
    if config:
        if config.nome_subunidade:
            nome_cabecalho = f"{config.nome_unidade} - {config.nome_subunidade}"
        else:
            nome_cabecalho = config.nome_unidade
    else:
        nome_cabecalho = "Unidade Militar"
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="escalas_{servico.nome}.pdf"'
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    timestamp = datetime.now().strftime('Exportado em: %d/%m/%Y %H:%M')
    
    def draw_header():
        p.setFont("Helvetica-Bold", 16)
        p.drawString(2*cm, height-2*cm, nome_cabecalho)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(2*cm, height-3*cm, f"Escalas do Serviço – {servico.nome}")
        p.setFont("Helvetica", 10)

    def draw_footer():
        p.setFont("Helvetica", 8)
        p.drawRightString(width-2*cm, 1.5*cm, timestamp)

    draw_header()
    draw_footer()
    y = height-4*cm
    
    # Cabeçalho da tabela
    p.setFillColor(colors.HexColor('#4A5D23'))
    p.rect(2*cm, y, width-4*cm, 0.7*cm, fill=1)
    p.setFillColor(colors.white)
    p.drawString(2.1*cm, y+0.2*cm, "Tipo")
    p.drawString(4*cm, y+0.2*cm, "Efetivos")
    p.drawString(10*cm, y+0.2*cm, "Reservas")
    p.drawString(15*cm, y+0.2*cm, "Observações")
    y -= 0.7*cm
    
    for escala in escalas:
        if y < 2*cm:
            p.showPage()
            draw_header()
            draw_footer()
            y = height-3*cm
            p.setFont("Helvetica", 10)
            y -= 1*cm
            p.setFillColor(colors.HexColor('#4A5D23'))
            p.rect(2*cm, y, width-4*cm, 0.7*cm, fill=1)
            p.setFillColor(colors.white)
            p.drawString(2.1*cm, y+0.2*cm, "Tipo")
            p.drawString(4*cm, y+0.2*cm, "Efetivos")
            p.drawString(10*cm, y+0.2*cm, "Reservas")
            p.drawString(15*cm, y+0.2*cm, "Observações")
            y -= 0.7*cm
            
        tipo = "B" if escala.e_escala_b else "A"
        efetivos = ", ".join([
            f"{mim.militar.posto} {mim.militar.nome}" for mim in escala.militares_info.all() if not mim.e_reserva
        ])
        reservas = ", ".join([
            f"{mim.militar.posto} {mim.militar.nome}" for mim in escala.militares_info.all() if mim.e_reserva
        ])
        obs = escala.observacoes[:40] if escala.observacoes else ""
        
        # Destacar Escala B
        if getattr(escala, 'e_escala_b', False):
            p.saveState()
            p.setFillColor(colors.HexColor('#e6f2d8'))
            p.rect(2*cm, y, width-4*cm, 0.6*cm, fill=1, stroke=0)
            p.restoreState()
            p.setFont("Helvetica-Bold", 9)
            p.setFillColor(colors.HexColor('#4A5D23'))
        else:
            p.setFont("Helvetica", 9)
            p.setFillColor(colors.black)
            
        p.drawString(2.1*cm, y+0.1*cm, tipo)
        p.drawString(4*cm, y+0.1*cm, efetivos if efetivos else "—")
        p.drawString(10*cm, y+0.1*cm, reservas if reservas else "—")
        p.drawString(15*cm, y+0.1*cm, obs)
        y -= 0.6*cm
        
    p.showPage()
    p.save()
    return response

@login_required
def obter_militar(request, militar_nim):
    try:
        militar = Militar.objects.get(nim=militar_nim)
        return JsonResponse({
            'success': True,
            'nim': militar.nim,
            'nome': militar.nome,
            'posto': militar.posto
        })
    except Militar.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Militar não encontrado'
        }, status=404)

@login_required
def obter_militares_disponiveis(request, servico_id, data):
    try:
        servico = Servico.objects.get(id=servico_id)
        data = datetime.strptime(data, '%Y-%m-%d').date()
        
        # Obter militares que já estão nomeados como efetivos para esta data
        militares_efetivos = Nomeacao.objects.filter(
            data=data,
            escala_militar__escala__servico=servico,
            e_reserva=False
        ).values_list('escala_militar__militar__nim', flat=True)
        
        # Obter militares disponíveis (que não estão nomeados como efetivos)
        militares_disponiveis = Militar.objects.filter(
            servicos=servico
        ).exclude(
            nim__in=militares_efetivos
        ).values('nim', 'nome', 'posto')
        
        return JsonResponse({
            'success': True,
            'militares': list(militares_disponiveis)
        })
    except (Servico.DoesNotExist, ValueError):
        return JsonResponse({
            'success': False,
            'message': 'Dados inválidos'
        }, status=400)

@login_required
def substituir_militar(request):
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Método não permitido'
        }, status=405)
    
    try:
        data = json.loads(request.body)
        militar_atual = Militar.objects.get(nim=data['militar_atual'])
        novo_militar = Militar.objects.get(nim=data['novo_militar'])
        servico = Servico.objects.get(id=data['servico'])
        data_substituicao = datetime.strptime(data['data'], '%Y-%m-%d').date()
        e_reserva = data['e_reserva']
        observacoes = data.get('observacoes', '')
        
        # Remover nomeação atual
        nomeacao_atual = Nomeacao.objects.get(
            escala_militar__militar=militar_atual,
            escala_militar__escala__servico=servico,
            data=data_substituicao,
            e_reserva=e_reserva
        )
        
        # Obter a primeira escala do serviço
        escala = Escala.objects.filter(servico=servico).order_by('id').first()
        escala_militar = EscalaMilitar.objects.get_or_create(
            escala=escala,
            militar=novo_militar
        )[0]
        
        nova_nomeacao = Nomeacao.objects.create(
            escala_militar=escala_militar,
            data=data_substituicao,
            e_reserva=e_reserva,
            observacoes=observacoes
        )
        
        # Remover nomeação antiga
        nomeacao_atual.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Substituição realizada com sucesso'
        })
    except (Militar.DoesNotExist, Servico.DoesNotExist, Nomeacao.DoesNotExist, ValueError, KeyError) as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)

@login_required
def obter_nomeacao_atual(request, servico_id, data, tipo):
    try:
        servico = Servico.objects.get(id=servico_id)
        data = datetime.strptime(data, '%Y-%m-%d').date()
        e_reserva = tipo.lower() == 'true'
        
        nomeacao = Nomeacao.objects.filter(
            escala_militar__escala__servico=servico,
            data=data,
            e_reserva=e_reserva
        ).select_related('escala_militar__militar').first()
        
        if nomeacao:
            return JsonResponse({
                'success': True,
                'militar': {
                    'nim': nomeacao.escala_militar.militar.nim,
                    'nome': nomeacao.escala_militar.militar.nome,
                    'posto': nomeacao.escala_militar.militar.posto
                }
            })
        else:
            return JsonResponse({
                'success': True,
                'militar': None
            })
    except (Servico.DoesNotExist, ValueError):
        return JsonResponse({
            'success': False,
            'message': 'Dados inválidos'
        }, status=400)

@login_required
def editar_observacao_nomeacao(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método não permitido'}, status=405)
    try:
        data = json.loads(request.body)
        servico = Servico.objects.get(id=data['servico'])
        data_nomeacao = datetime.strptime(data['data'], '%Y-%m-%d').date()
        observacoes = data.get('observacoes', '')

        nomeacoes = Nomeacao.objects.filter(
            escala_militar__escala__servico=servico,
            data=data_nomeacao
        )
        if not nomeacoes.exists():
            return JsonResponse({'success': False, 'message': 'Nomeação não encontrada.'}, status=404)
        nomeacoes.update(observacoes=observacoes)
        return JsonResponse({'success': True, 'message': 'Observação atualizada com sucesso.'})
    except (Servico.DoesNotExist, ValueError, KeyError) as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@csrf_exempt  # Se usares AJAX puro, pode ser necessário. Se usares o CSRF token, podes remover.
@require_POST
def atualizar_ordem_militares(request, escala_id):
    try:
        data = json.loads(request.body)
        nova_ordem = data.get('ordem', [])  # lista de NIMs na nova ordem
        escala = Escala.objects.get(id=escala_id)
        for idx, nim in enumerate(nova_ordem):
            try:
                em = EscalaMilitar.objects.get(escala=escala, militar__nim=nim)
                em.ordem = idx + 1
                em.save()
            except EscalaMilitar.DoesNotExist:
                continue
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return HttpResponseBadRequest(str(e))
