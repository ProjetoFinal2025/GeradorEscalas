from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from datetime import datetime, timedelta, date
from .models import Servico, Dispensa, Escala, Militar, EscalaMilitar, Nomeacao, TrocaServico
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
from .services.troca_service import TrocaService
import json

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
    # Serviços ativos
    servicos = Servico.objects.filter(ativo=True)
    militares_por_servico = {s.nome: s.militares.count() for s in servicos}
    total_militares = sum(militares_por_servico.values())

    # Militares dispensados atualmente
    hoje = date.today()
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

    # Últimas 10 ações do utilizador (opcional)
    recent_actions = (
        LogEntry.objects.filter(user=request.user)
        .select_related("content_type")
        .order_by("-action_time")[:10]
    )

    context = {
        'servicos': servicos,
        'militares_por_servico': militares_por_servico,
        'total_militares': total_militares,
        'total_dispensados': total_dispensados,
        'top_militares': top_militares,
        'recent_actions': recent_actions,
        'hoje': hoje,
    }
    return render(request, 'core/home.html', context)

@login_required
def mapa_dispensas_view(request):
    # Obter serviços ativos
    servicos = Servico.objects.filter(ativo=True)
    # Obter período
    hoje = date.today()
    data_fim = hoje + timedelta(days=30)
    # Obter feriados
    feriados = obter_feriados(hoje, data_fim)
    # Obter dispensas
    dispensas = Dispensa.objects.filter(
        data_inicio__lte=data_fim,
        data_fim__gte=hoje
    ).select_related('militar')
    context = {
        'servicos': servicos,
        'dispensas': dispensas,
        'feriados': feriados,
        'hoje': hoje,
        'data_fim': data_fim
    }
    return render(request, 'core/mapa_dispensas.html', context)

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

@staff_member_required
def nomear_militares_view(request):
    servicos = Servico.objects.filter(ativo=True)
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
        for servico in servicos:
            tabela[d][servico.id] = {'efetivo': [], 'reserva': []}
    for n in nomeacoes:
        servico_id = n.escala_militar.escala.servico_id
        if n.e_reserva:
            tabela[n.data][servico_id]['reserva'].append(n.escala_militar.militar)
        else:
            tabela[n.data][servico_id]['efetivo'].append(n.escala_militar.militar)
    return render(request, 'core/lista_servicos.html', {
        'servicos': servicos,
        'datas': datas,
        'tabela': tabela,
    })

@login_required
def previsoes_por_servico_view(request):
    servicos = Servico.objects.filter(ativo=True)
    if request.method == 'POST':
        servico_id = request.POST.get('servico_id')
        if servico_id:
            return redirect('previsoes_servico', servico_id=servico_id)
    return render(request, 'core/previsoes_por_servico.html', {'servicos': servicos})

@login_required
def previsoes_servico_view(request, servico_id):
    servico = get_object_or_404(Servico, id=servico_id)
    hoje = date.today()
    
    # Verificar se há nomeações para o dia atual
    nomeacoes_hoje = Nomeacao.objects.filter(
        escala_militar__escala__servico=servico,
        data=hoje
    ).exists()
    
    if nomeacoes_hoje:
        messages.error(request, ERRO_PREVISAO_DIA_ATUAL)
        return redirect('previsoes_por_servico')
    
    # Obter todas as nomeações futuras para o serviço
    nomeacoes = Nomeacao.objects.filter(
        escala_militar__escala__servico=servico,
        data__gte=hoje
    ).select_related('escala_militar__militar', 'escala_militar__escala').order_by('data')
    
    # Se não houver nomeações, retornar lista vazia
    if not nomeacoes.exists():
        return render(request, 'core/previsoes_servico.html', {
            'servico': servico,
            'dias': [],
            'nomeacoes_por_data': {},
            'observacoes_por_data': {},
        })
    
    # Obter a data da última nomeação
    data_fim = nomeacoes.last().data
    
    # Obter feriados
    feriados = obter_feriados(hoje, data_fim)
    feriados_set = set(feriados)
    
    # Gerar todos os dias do intervalo
    dias = []
    data_atual = hoje
    while data_atual <= data_fim:
        if data_atual in feriados_set:
            tipo_dia = 'feriado'
        elif data_atual.weekday() >= 5:
            tipo_dia = 'fim_semana'
        else:
            tipo_dia = 'util'
        dias.append({'data': data_atual, 'tipo_dia': tipo_dia})
        data_atual += timedelta(days=1)
    
    # Agrupar por data
    nomeacoes_por_data = {}
    observacoes_por_data = {}
    for n in nomeacoes:
        nomeacoes_por_data.setdefault(n.data, {'efetivos': [], 'reservas': []})
        if n.e_reserva:
            nomeacoes_por_data[n.data]['reservas'].append(n.escala_militar.militar)
        else:
            nomeacoes_por_data[n.data]['efetivos'].append(n.escala_militar.militar)
        # Guardar observações da escala
        observacoes_por_data[n.data] = n.escala_militar.escala.observacoes if n.escala_militar.escala else ''
    
    return render(request, 'core/previsoes_servico.html', {
        'servico': servico,
        'dias': dias,
        'nomeacoes_por_data': nomeacoes_por_data,
        'observacoes_por_data': observacoes_por_data,
    })

@login_required
def exportar_previsoes_pdf(request, servico_id):
    servico = get_object_or_404(Servico, id=servico_id)
    
    # Obter todas as nomeações do serviço
    nomeacoes = Nomeacao.objects.filter(
        escala_militar__escala__servico=servico
    ).select_related('escala_militar__militar', 'escala_militar__escala').order_by('data')
    
    if not nomeacoes.exists():
        messages.error(request, "Não existem nomeações para exportar.")
        return redirect('previsoes_servico', servico_id=servico_id)
    
    # Obter data inicial e final das nomeações
    data_inicio = nomeacoes.first().data
    data_fim = nomeacoes.last().data
    
    # Obter feriados para o intervalo
    feriados = obter_feriados(data_inicio, data_fim)
    feriados_set = set(feriados)
    
    # Gerar todos os dias do intervalo
    dias = []
    data_atual = data_inicio
    while data_atual <= data_fim:
        if data_atual in feriados_set:
            tipo_dia = 'feriado'
        elif data_atual.weekday() >= 5:
            tipo_dia = 'fim_semana'
        else:
            tipo_dia = 'util'
        dias.append({'data': data_atual, 'tipo_dia': tipo_dia})
        data_atual += timedelta(days=1)
    
    # Agrupar nomeações por data
    nomeacoes_por_data = {}
    observacoes_por_data = {}
    for n in nomeacoes:
        nomeacoes_por_data.setdefault(n.data, {'efetivo': None, 'reserva': None})
        if n.e_reserva:
            nomeacoes_por_data[n.data]['reserva'] = n.escala_militar.militar
        else:
            nomeacoes_por_data[n.data]['efetivo'] = n.escala_militar.militar
        observacoes_por_data[n.data] = n.escala_militar.escala.observacoes if n.escala_militar.escala else ''
    
    # Gerar PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="previsoes_{servico.nome}.pdf"'
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    timestamp = datetime.now().strftime('Exportado em: %d/%m/%Y %H:%M')
    
    def draw_header():
        p.setFont("Helvetica-Bold", 16)
        p.drawString(2*cm, height-2*cm, f"Previsões de Nomeação – {servico.nome}")
        p.setFont("Helvetica", 8)
        p.drawRightString(width-2*cm, height-1.5*cm, timestamp)
        p.setFont("Helvetica", 10)
    
    draw_header()
    y = height-3*cm
    
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
            y = height-2*cm
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
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="escalas_{servico.nome}.pdf"'
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    timestamp = datetime.now().strftime('Exportado em: %d/%m/%Y %H:%M')
    def draw_header():
        p.setFont("Helvetica-Bold", 16)
        p.drawString(2*cm, height-2*cm, f"Escalas do Serviço – {servico.nome}")
        p.setFont("Helvetica", 8)
        p.drawRightString(width-2*cm, height-1.5*cm, timestamp)
        p.setFont("Helvetica", 10)
    draw_header()
    y = height-3*cm
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
            y = height-2*cm
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
def solicitar_troca_view(request):
    if request.method == 'POST':
        militar_trocado_id = request.POST.get('militar_trocado')
        data_troca_str = request.POST.get('data_troca')
        
        try:
            militar_solicitante = request.user.militar
            militar_trocado = Militar.objects.get(nim=militar_trocado_id)
            data_troca = datetime.strptime(data_troca_str, '%Y-%m-%d').date()
            
            troca_service = TrocaService()
            sucesso, mensagem = troca_service.solicitar_troca(
                militar_solicitante,
                militar_trocado,
                data_troca
            )
            
            if sucesso:
                messages.success(request, mensagem)
            else:
                messages.error(request, mensagem)
                
        except (Militar.DoesNotExist, ValueError):
            messages.error(request, "Dados inválidos")
            
        return redirect('solicitar_troca')
    
    # Obter militares disponíveis para troca
    militares_disponiveis = Militar.objects.filter(
        servicos__in=request.user.militar.servicos.all()
    ).exclude(
        nim=request.user.militar.nim
    ).distinct()
    
    # Obter trocas pendentes e aprovadas
    trocas_pendentes = TrocaService.obter_trocas_pendentes()
    trocas_aprovadas = TrocaService.obter_trocas_por_militar(request.user.militar).filter(
        status='APROVADA'
    )
    
    context = {
        'militares_disponiveis': militares_disponiveis,
        'trocas_pendentes': trocas_pendentes,
        'trocas_aprovadas': trocas_aprovadas
    }
    
    return render(request, 'core/solicitar_troca.html', context)

@login_required
def aprovar_troca_view(request, troca_id):
    troca = get_object_or_404(TrocaServico, id=troca_id)
    
    if request.method == 'POST':
        troca_service = TrocaService()
        sucesso, mensagem = troca_service.aprovar_troca(troca)
        
        if sucesso:
            messages.success(request, mensagem)
        else:
            messages.error(request, mensagem)
            
    return redirect('solicitar_troca')

@login_required
def rejeitar_troca_view(request, troca_id):
    troca = get_object_or_404(TrocaServico, id=troca_id)
    
    if request.method == 'POST':
        troca_service = TrocaService()
        sucesso, mensagem = troca_service.rejeitar_troca(troca)
        
        if sucesso:
            messages.success(request, mensagem)
        else:
            messages.error(request, mensagem)
            
    return redirect('solicitar_troca')

@login_required
def agendar_destroca_view(request, troca_id):
    troca = get_object_or_404(TrocaServico, id=troca_id)
    
    if request.method == 'POST':
        data_destroca_str = request.POST.get('data_destroca')
        
        try:
            data_destroca = datetime.strptime(data_destroca_str, '%Y-%m-%d').date()
            
            troca_service = TrocaService()
            sucesso, mensagem = troca_service.agendar_destroca(troca, data_destroca)
            
            if sucesso:
                messages.success(request, mensagem)
            else:
                messages.error(request, mensagem)
                
        except ValueError:
            messages.error(request, "Data inválida")
            
    return redirect('solicitar_troca')

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
