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

        # Gerar previsões para cada dia
        data_atual = data_inicio
        while data_atual <= data_fim:
            # Determinar se é escala A ou B
            e_fim_semana = data_atual.weekday() >= 5
            e_feriado = data_atual in feriados
            e_escala_b = e_fim_semana or e_feriado

            # Se é escala B e o serviço não tem escala B, pular
            if e_escala_b and not servico.tem_escala_B:
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

            # Encontrar próximo militar disponível
            militar_encontrado = False
            tentativas = 0
            while not militar_encontrado and tentativas < total_militares:
                militar = militares[indice_militar]
                disponivel = True

                # Verificar dispensas
                if Dispensa.objects.filter(
                    militar=militar,
                    data_inicio__lte=data_atual,
                    data_fim__gte=data_atual
                ).exists():
                    disponivel = False

                # Verificar se já está nomeado para outra escala no mesmo dia
                if EscalaMilitar.objects.filter(
                    escala__data=data_atual,
                    militar=militar
                ).exists():
                    disponivel = False

                # Calcular folga
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
                        ordem_semana=1 if not e_escala_b else None,
                        ordem_fds=1 if e_escala_b else None
                    )
                    militar_encontrado = True

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