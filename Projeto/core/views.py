from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from .models import Servico, Dispensa, Escala
from datetime import datetime, timedelta, date


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
    print("=== DEBUG ===")
    print("Serviços ativos encontrados:", [f"{s.id}: {s.nome}" for s in todos_servicos])
    
    # Obtém o serviço selecionado ou o primeiro serviço ativo
    servico_id = request.GET.get('servico_id')
    print("Serviço ID recebido:", servico_id)
    
    if servico_id:
        servico = get_object_or_404(Servico, pk=servico_id, ativo=True)
        print("Serviço encontrado por ID:", f"{servico.id}: {servico.nome}")
    else:
        servico = Servico.objects.filter(ativo=True).first()
        print("Primeiro serviço ativo:", f"{servico.id}: {servico.nome}" if servico else "Nenhum")
        if not servico:
            messages.warning(request, "Não existem serviços ativos.")
            return render(request, 'core/home.html')

    # Verifica se é visualização de previsão
    tipo_visualizacao = request.GET.get('tipo', 'atual')
    print("Tipo de visualização:", tipo_visualizacao)
    
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

    print("Período:", data_inicio, "a", data_fim)

    # Busca as escalas do período
    escalas = Escala.objects.filter(
        servico=servico,
        data__range=[data_inicio, data_fim]
    ).order_by('data')
    print("Escalas encontradas:", escalas.count())
    for escala in escalas:
        print(f"Escala: {escala.data} - Militar: {escala.militar.nome if escala.militar else 'Nenhum'}")

    # Lista de serviços ativos para o seletor
    servicos_ativos = Servico.objects.filter(ativo=True)
    print("Serviços ativos para o seletor:", [f"{s.id}: {s.nome}" for s in servicos_ativos])
    print("=== FIM DEBUG ===")

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
    # Obter todos os serviços
    servicos = Servico.objects.filter(ativo=True)
    
    # Dicionário para armazenar as dispensas por serviço
    mapa_dispensas = {}
    
    # Para cada serviço, obter as dispensas dos militares
    for servico in servicos:
        militares = servico.militares.all()
        dispensas_servico = []
        
        for militar in militares:
            dispensas = Dispensa.objects.filter(militar=militar)
            for dispensa in dispensas:
                dispensas_servico.append({
                    'militar': f"{militar.posto} {militar.nome}",
                    'data_inicio': dispensa.data_inicio,
                    'data_fim': dispensa.data_fim,
                    'motivo': dispensa.motivo
                })
        
        mapa_dispensas[servico.nome] = sorted(
            dispensas_servico, 
            key=lambda x: x['data_inicio']
        )
    
    return render(request, 'mapa_dispensas.html', {
        'mapa_dispensas': mapa_dispensas,
        'data_atual': datetime.now().date()
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
