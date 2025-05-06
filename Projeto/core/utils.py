from datetime import date, timedelta
from .models import Escala, EscalaMilitar, RegraNomeacao, Dispensa, Feriado

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
    feriados_personalizados = Feriado.objects.filter(
        data__gte=data_inicio,
        data__lte=data_fim
    )
    feriados.extend([f.data for f in feriados_personalizados])
    
    # Filtra apenas os feriados dentro do período especificado
    feriados = [f for f in feriados if data_inicio <= f <= data_fim]
    
    return sorted(list(set(feriados)))  # Remove duplicatas e ordena 