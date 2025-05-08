from datetime import date, timedelta
from .models import Escala, EscalaMilitar, RegraNomeacao, Dispensa, Feriado
from typing import List

def calcular_pascoa(ano: int) -> date:
    """
    Calcula a data da Páscoa para um determinado ano usando o algoritmo de Meeus/Jones/Butcher.
    """
    a = ano % 19
    b = ano // 100
    c = ano % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    
    return date(ano, mes, dia)

def calcular_feriados_moveis(ano: int) -> List[date]:
    """
    Calcula todos os feriados móveis para um determinado ano.
    Retorna uma lista de datas com os feriados móveis.
    """
    pascoa = calcular_pascoa(ano)
    
    # Carnaval (47 dias antes da Páscoa)
    carnaval = pascoa - timedelta(days=47)
    
    # Sexta-feira Santa (2 dias antes da Páscoa)
    sexta_santa = pascoa - timedelta(days=2)
    
    # Domingo de Páscoa (já calculado)
    
    # Segunda-feira de Páscoa (dia seguinte à Páscoa)
    segunda_pascoa = pascoa + timedelta(days=1)
    
    # Corpo de Deus (60 dias após a Páscoa)
    corpo_deus = pascoa + timedelta(days=60)
    
    return [
        carnaval,      # Carnaval
        sexta_santa,   # Sexta-feira Santa
        pascoa,        # Domingo de Páscoa
        segunda_pascoa,# Segunda-feira de Páscoa
        corpo_deus     # Corpo de Deus
    ]

def obter_feriados(data_inicio: date = None, data_fim: date = None) -> List[date]:
    """
    Obtém todos os feriados no período especificado.
    Se não forem fornecidas datas, usa o ano atual.
    """
    if data_inicio is None:
        data_inicio = date.today()
    if data_fim is None:
        data_fim = date(data_inicio.year, 12, 31)
    
    feriados = []
    
    # Adiciona feriados fixos
    for ano in range(data_inicio.year, data_fim.year + 1):
        feriados.extend([
            date(ano, 1, 1),    # Ano Novo
            date(ano, 4, 25),   # Dia da Liberdade
            date(ano, 5, 1),    # Dia do Trabalhador
            date(ano, 6, 10),   # Dia de Portugal
            date(ano, 8, 15),   # Assunção de Nossa Senhora
            date(ano, 10, 5),   # Implantação da República
            date(ano, 11, 1),   # Todos os Santos
            date(ano, 12, 1),   # Restauração da Independência
            date(ano, 12, 8),   # Imaculada Conceição
            date(ano, 12, 25),  # Natal
        ])
        
        # Adiciona feriados móveis
        feriados.extend(calcular_feriados_moveis(ano))
    
    # Adiciona feriados personalizados do banco de dados
    feriados.extend(
        list(Feriado.objects.filter(data__gte=data_inicio, data__lte=data_fim).values_list('data', flat=True))
    )
    
    # Filtra apenas os feriados dentro do período e remove duplicatas
    feriados = [f for f in feriados if data_inicio <= f <= data_fim]
    return sorted(list(set(feriados))) 