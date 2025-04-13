from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from .models import Servico, Dispensa
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
def home_view(request):
    return HttpResponse("Login realizado com sucesso. Estás a ver Casa")

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

def obter_feriados(ano):
    """Retorna lista de feriados para o ano especificado"""
    feriados = []
    
    # Adiciona feriados nacionais
    feriados.extend([
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
    ])
    
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
    feriados_personalizados = Feriado.objects.filter(data__year=ano)
    feriados.extend([f.data for f in feriados_personalizados])
    
    return sorted(list(set(feriados)))  # Remove duplicatas e ordena
