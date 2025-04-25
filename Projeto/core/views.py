from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from datetime import datetime, timedelta, date
from .models import Servico, Dispensa, Escala, Militar, EscalaMilitar
from .services.nomeacao_service import NomeacaoService


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
    """View da página inicial com visualização das escalas"""
    # Debug: Imprimir todos os serviços ativos
    todos_servicos = Servico.objects.filter(ativo=True)


    # Obtém o serviço selecionado ou o primeiro serviço ativo
    servico_id = request.GET.get('servico_id')

    if servico_id:
        servico = get_object_or_404(Servico, pk=servico_id, ativo=True)
    else:
        servico = Servico.objects.filter(ativo=True).first()
        if not servico:
            messages.warning(request, "Não existem serviços ativos.")
            return render(request, 'core/home.html')

    # Verifica se é visualização de previsão
    tipo_visualizacao = request.GET.get('tipo', 'atual')

    # Define o período
    hoje = date.today()
    if tipo_visualizacao == 'previsao':
        # Para previsão, mostra o próximo mês
        if hoje.month == 12:
            data_inicio = date(hoje.year + 1, 1, 1)
            data_fim = date(hoje.year + 1, 2, 1) - timedelta(days=1)
        else:
            data_inicio = date(hoje.year, hoje.month + 1, 1)
            data_fim = date(hoje.year, hoje.month + 2, 1) - timedelta(days=1)
    else:
        # Para visualização atual, mostra o mês atual
        data_inicio = date(hoje.year, hoje.month, 1)
        if hoje.month == 12:
            data_fim = date(hoje.year + 1, 1, 1) - timedelta(days=1)
        else:
            data_fim = date(hoje.year, hoje.month + 1, 1) - timedelta(days=1)

    # Busca as escalas do período
    escalas = Escala.objects.filter(
        servico=servico,
        data__range=[data_inicio, data_fim]
    ).order_by('data')

    # Lista de serviços ativos para o seletor
    servicos_ativos = Servico.objects.filter(ativo=True)


    context = {
        'servico': servico,
        'servicos_ativos': servicos_ativos,
        'escalas': escalas,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'tipo_visualizacao': tipo_visualizacao,
    }

    return render(request, 'core/home.html', context)

@login_required
def mapa_dispensas_view(request):
    servico_id = request.GET.get('servico')
    servico_selecionado = None
    servicos = Servico.objects.filter(ativo=True)
    
    if servico_id:
        servico_selecionado = get_object_or_404(Servico, id=servico_id, ativo=True)
        servicos = [servico_selecionado]
    
    hoje = timezone.now().date()
    dias = []
    for i in range(30):  # Próximos 30 dias
        dia = hoje + timedelta(days=i)
        dias.append({'data': dia, 'dia_semana': dia.strftime('%A')})
    
    mapa_dispensas = {}
    for servico in servicos:
        militares = servico.militares.all()
        dispensas_servico = {}
        
        for militar in militares:
            dispensas = {}
            for dia in dias:
                dispensa = Dispensa.objects.filter(
                    militar=militar,
                    data_inicio__lte=dia['data'],
                    data_fim__gte=dia['data'],
                    ativo=True
                ).first()
                if dispensa:
                    dispensas[dia['data']] = dispensa
            dispensas_servico[militar] = dispensas
        
        mapa_dispensas[servico] = {
            'militares': dispensas_servico
        }
    
    return render(request, 'admin/mapa_dispensas_test.html', {
        'mapa_dispensas': mapa_dispensas,
        'dias': dias,
        'servicos': Servico.objects.filter(ativo=True),
        'servico_selecionado': servico_selecionado
    })

@login_required
def escala_servico_view(request, servico_id=None):
    """View para exibir a escala de um serviço específico"""
    
    # Se não foi especificado um serviço, pega o primeiro serviço ativo
    if servico_id is None:
        servico = Servico.objects.filter(ativo=True).first()
        if not servico:
            messages.error(request, "Não existem serviços ativos.")
            return redirect('home')
    else:
        servico = get_object_or_404(Servico, pk=servico_id, ativo=True)

    # Verifica se é visualização de previsão
    tipo_visualizacao = request.GET.get('tipo', 'atual')
    
    # Define o período
    hoje = date.today()
    if tipo_visualizacao == 'previsao':
        # Para previsão, mostra o próximo mês
        if hoje.month == 12:
            data_inicio = date(hoje.year + 1, 1, 1)
            data_fim = date(hoje.year + 1, 2, 1) - timedelta(days=1)
        else:
            data_inicio = date(hoje.year, hoje.month + 1, 1)
            data_fim = date(hoje.year, hoje.month + 2, 1) - timedelta(days=1)
    else:
        # Para visualização atual, mostra o mês atual
        data_inicio = date(hoje.year, hoje.month, 1)
        if hoje.month == 12:
            data_fim = date(hoje.year + 1, 1, 1) - timedelta(days=1)
        else:
            data_fim = date(hoje.year, hoje.month + 1, 1) - timedelta(days=1)

    # Busca as escalas do período com os militares nomeados
    escalas = Escala.objects.filter(
        servico=servico,
        data__range=[data_inicio, data_fim]
    ).prefetch_related(
        'militares_info__militar'
    ).order_by('data')

    # Lista de serviços ativos para o seletor
    servicos_ativos = Servico.objects.filter(ativo=True)

    context = {
        'servico': servico,
        'servicos_ativos': servicos_ativos,
        'escalas': escalas,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'tipo_visualizacao': tipo_visualizacao,
    }

    return render(request, 'core/escala_servico.html', context)

@login_required
def gerar_escalas_view(request):
    """
    View para gerar escalas automaticamente
    """
    if request.method == 'POST':
        servico_id = request.POST.get('servico')
        data_inicio = request.POST.get('data_inicio')
        data_fim = request.POST.get('data_fim')

        try:
            servico = Servico.objects.get(id=servico_id)
            data_inicio = date.fromisoformat(data_inicio)
            data_fim = date.fromisoformat(data_fim)

            from .utils import gerar_escalas_automaticamente
            if gerar_escalas_automaticamente(servico, data_inicio, data_fim):
                messages.success(request, "Escalas geradas com sucesso!")
                # Redireciona para a previsão com o serviço selecionado
                return redirect(f'/admin/core/previsaoescalasproxy/?servico={servico_id}&data_fim={data_fim}')
            else:
                messages.error(request, "Erro ao gerar previsões.")
        except Exception as e:
            messages.error(request, f"Erro: {str(e)}")

        return redirect('admin:core_previsaoescalasproxy_changelist')

    # Lista de serviços ativos para o seletor
    servicos = Servico.objects.filter(ativo=True)
    
    context = {
        'servicos': servicos,
        'hoje': date.today(),
        'proximo_mes': date.today().replace(day=1) + timedelta(days=32),
    }
    
    return render(request, 'admin/core/escala/gerar_previsoes.html', context)

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
def nomear_militares(request):
    servicos = Servico.objects.filter(ativo=True)
    servico_selecionado = None
    data = None
    militares_disponiveis = []
    
    if request.method == 'GET':
        servico_id = request.GET.get('servico')
        data_str = request.GET.get('data')
        
        if servico_id and data_str:
            try:
                servico_selecionado = Servico.objects.get(id=servico_id)
                data = date.fromisoformat(data_str)
                nomeacao_service = NomeacaoService(servico_selecionado)
                militares_disponiveis = nomeacao_service.obter_militares_disponiveis(data)
            except (Servico.DoesNotExist, ValueError):
                messages.error(request, 'Dados inválidos fornecidos.')
    
    elif request.method == 'POST':
        servico_id = request.POST.get('servico')
        data_str = request.POST.get('data')
        militar_id = request.POST.get('militar')
        
        if servico_id and data_str and militar_id:
            try:
                servico = Servico.objects.get(id=servico_id)
                militar = Militar.objects.get(id=militar_id)
                data = date.fromisoformat(data_str)
                posicao = request.POST.get(f'posicao_{militar_id}')
                
                nomeacao_service = NomeacaoService(servico)
                if nomeacao_service.criar_nomeacao(militar, servico, data, posicao):
                    messages.success(request, f'Militar {militar.nome} nomeado com sucesso!')
                else:
                    messages.error(request, 'Não foi possível nomear o militar. Verifique se ele está disponível.')
                
                return redirect('nomear_militares')
            except (Servico.DoesNotExist, Militar.DoesNotExist, ValueError):
                messages.error(request, 'Dados inválidos fornecidos.')
    
    context = {
        'servicos': servicos,
        'servico_selecionado': servico_selecionado,
        'data': data,
        'militares_disponiveis': militares_disponiveis,
    }
    
    return render(request, 'core/nomear_militares.html', context)
