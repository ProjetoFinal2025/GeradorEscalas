from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from datetime import datetime, timedelta, date
from .models import Servico, Dispensa, Escala, Militar, EscalaMilitar
from .forms import *
from .services.escala_service import EscalaService
from .utils import obter_feriados
from django.db.models import Q
from django.core.paginator import Paginator


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
    # Obter serviços ativos
    servicos = Servico.objects.filter(ativo=True)
    
    # Obter escalas do dia
    hoje = date.today()
    escalas_hoje = Escala.objects.filter(
        data=hoje
    ).prefetch_related(
        'militares_info__militar'
    )
    
    # Obter feriados do mês
    data_fim = hoje.replace(day=1) + timedelta(days=32)
    feriados = obter_feriados(hoje, data_fim)
    
    context = {
        'servicos': servicos,
        'escalas_hoje': escalas_hoje,
        'feriados': feriados,
        'hoje': hoje
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
        data__gte=hoje,
        data__lte=data_fim
    ).order_by('data')
    
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
