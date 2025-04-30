from datetime import date, timedelta
from django.utils import timezone
from .models import Servico, Militar, Escala, EscalaMilitar, RegraNomeacao, Dispensa, Feriado

def gerar_escalas_automaticamente(servico, data_inicio, data_fim):
    """
    Gera escalas automaticamente para um serviço no período especificado
    """
    try:
        # Obter regras de nomeação
        regras = RegraNomeacao.objects.filter(servico=servico)
        regra_mesma_escala = regras.filter(tipo_folga='mesma_escala').first()
        regra_entre_escalas = regras.filter(tipo_folga='entre_escalas').first()

        # Obter militares do serviço ordenados por posto e antiguidade
        militares = list(servico.militares.all().order_by('posto', 'nim'))
        if not militares:
            return False

        # Obter feriados
        feriados = obter_feriados(data_inicio, data_fim)

        # Índice para controlar qual militar será nomeado
        indice_militar = 0
        total_militares = len(militares)
        militares_disponiveis = set(militares)  # Conjunto de militares ainda não nomeados

        # Gerar previsões para cada dia
        data_atual = data_inicio
        while data_atual <= data_fim:
            # Determinar se é escala A ou B
            e_fim_semana = data_atual.weekday() >= 5
            e_feriado = data_atual in feriados
            e_escala_b = e_fim_semana or e_feriado

            # Se é escala B e o serviço não tem escala B, pular
            if e_escala_b and servico.tipo_escalas == "A":
                data_atual += timedelta(days=1)
                continue

            # Limpar escalas existentes para esta data
            Escala.objects.filter(
                servico=servico,
                data=data_atual,
                e_escala_b=e_escala_b
            ).delete()

            # Criar nova escala
            escala = Escala.objects.create(
                servico=servico,
                data=data_atual,
                e_escala_b=e_escala_b,
                prevista=True
            )

            # Nomear o número correto de militares
            militares_nomeados = 0
            tentativas = 0
            militares_tentados = set()  # Conjunto de militares já tentados neste dia

            while militares_nomeados < servico.n_elementos and tentativas < total_militares:
                militar = militares[indice_militar]
                disponivel = True

                # Se já tentamos todos os militares disponíveis, reinicia o conjunto
                if len(militares_tentados) == len(militares_disponiveis):
                    militares_disponiveis = set(militares)
                    militares_tentados.clear()

                # Verificar se o militar está disponível
                if militar not in militares_disponiveis:
                    disponivel = False

                # Verificar dispensas
                if disponivel and Dispensa.objects.filter(
                    militar=militar,
                    data_inicio__lte=data_atual,
                    data_fim__gte=data_atual
                ).exists():
                    disponivel = False
                    militares_disponiveis.remove(militar)

                # Verificar se já está nomeado para outra escala no mesmo dia
                if disponivel and EscalaMilitar.objects.filter(
                    escala__data=data_atual,
                    militar=militar
                ).exists():
                    disponivel = False
                    militares_disponiveis.remove(militar)

                # Calcular folga
                if disponivel:
                    folga = militar.calcular_folga(data_atual, servico)

                    # Verificar regras de folga
                    if e_escala_b and regra_mesma_escala:
                        if folga < regra_mesma_escala.horas_minimas:
                            disponivel = False
                    elif not e_escala_b and regra_entre_escalas:
                        if folga < regra_entre_escalas.horas_minimas:
                            disponivel = False

                if disponivel:
                    # Criar EscalaMilitar para o militar
                    EscalaMilitar.objects.create(
                        escala=escala,
                        militar=militar,
                        ordem_semana=militares_nomeados + 1 if not e_escala_b else None,
                        ordem_fds=militares_nomeados + 1 if e_escala_b else None,
                        e_reserva=militares_nomeados > 0  # O primeiro é efetivo, os outros são reserva
                    )
                    militares_nomeados += 1
                    militares_disponiveis.remove(militar)

                # Adicionar militar à lista de tentados
                militares_tentados.add(militar)

                # Avançar para o próximo militar
                indice_militar = (indice_militar + 1) % total_militares
                tentativas += 1

            data_atual += timedelta(days=1)

        return True
    except Exception as e:
        print(f"Erro ao gerar escalas: {str(e)}")
        return False

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