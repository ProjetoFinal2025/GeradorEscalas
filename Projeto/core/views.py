from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from .models import Servico, Dispensa, Escala
from datetime import datetime, timedelta, date, timezone


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

def obter_feriados(data_inicio=None, data_fim=None):
    """Retorna lista de feriados para o período especificado"""
    if data_inicio is None:
        data_inicio = date.today()
    if data_fim is None:
        data_fim = date(data_inicio.year, 12, 31)

    feriados = []
    anos = range(data_inicio.year, data_fim.year + 1)
    
    for ano in anos:
        # Adiciona feriados nacionais
        feriados_nacionais = [
            date(ano, 1, 1),   # Ano Novo
            date(ano, 4, 25),  # Dia da Liberdade
            date(ano, 5, 1),   # Dia do Trabalhador
            date(ano, 6, 10),  # Dia de Portugal
            date(ano, 8, 15),  # Assunção de Nossa Senhora
            date(ano, 10, 5),  # Implantação da República
            date(ano, 11, 1),  # Todos os Santos
            date(ano, 12, 1),  # Restauração da Independência
            date(ano, 12, 8),  # Imaculada Conceição
            date(ano, 12, 25), # Natal
        ]
        feriados.extend(feriados_nacionais)
        
        # Adiciona feriados móveis para 2024
        if ano == 2024:
            feriados.extend([
                date(2024, 2, 13),  # Carnaval
                date(2024, 3, 29),  # Sexta-feira Santa
                date(2024, 3, 31),  # Páscoa
                date(2024, 5, 30),  # Corpo de Deus
            ])
        elif ano == 2025:
            feriados.extend([
                date(2025, 3, 4),   # Carnaval
                date(2025, 4, 18),  # Sexta-feira Santa
                date(2025, 4, 20),  # Páscoa
                date(2025, 6, 19),  # Corpo de Deus
            ])
    
    # Adiciona feriados personalizados
    from .models import Feriado
    feriados_personalizados = Feriado.objects.filter(
        data__gte=data_inicio,
        data__lte=data_fim
    )
    feriados.extend([f.data for f in feriados_personalizados])
    
    # Filtra apenas os feriados dentro do período especificado
    feriados = [f for f in feriados if data_inicio <= f <= data_fim]
    
    return sorted(list(set(feriados)))  # Remove duplicatas e ordena

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
