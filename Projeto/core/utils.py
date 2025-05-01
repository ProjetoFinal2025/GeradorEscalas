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

        # Obter feriados
        feriados = obter_feriados(data_inicio, data_fim)

        # Dicionário para manter registro das últimas nomeações durante o processo
        ultimas_nomeacoes = {}
        # Inicializar com as últimas nomeações reais do banco de dados
        for militar in servico.militares.all():
            ultimo_servico = militar.obter_ultimo_servico(servico)
            if ultimo_servico:
                ultimas_nomeacoes[militar.nim] = ultimo_servico

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

            # Obter lista de militares disponíveis para este dia
            militares_disponiveis = []
            for militar in servico.militares.all():
                disponivel = True

                # Verificar dispensas
                if Dispensa.objects.filter(
                    militar=militar,
                    data_inicio__lte=data_atual,
                    data_fim__gte=data_atual
                ).exists():
                    disponivel = False
                    continue

                # Verificar se já está nomeado para outra escala no mesmo dia
                if EscalaMilitar.objects.filter(
                    escala__data=data_atual,
                    militar=militar
                ).exists():
                    disponivel = False
                    continue

                # Obter a última data de serviço (do dicionário ou data antiga se nunca fez serviço)
                ultima_data = ultimas_nomeacoes.get(militar.nim, date(1900, 1, 1))
                
                # Calcular folga baseada na última nomeação conhecida
                dias_folga = (data_atual - ultima_data).days
                horas_folga = dias_folga * 24  # Converter dias em horas

                # Verificar regras de folga
                if e_escala_b and regra_mesma_escala:
                    if horas_folga < regra_mesma_escala.horas_minimas:
                        disponivel = False
                        continue
                elif not e_escala_b and regra_entre_escalas:
                    if horas_folga < regra_entre_escalas.horas_minimas:
                        disponivel = False
                        continue

                if disponivel:
                    militares_disponiveis.append({
                        'militar': militar,
                        'ultimo_servico': ultima_data,
                        'posto': militar.posto,
                        'nim': militar.nim
                    })

            # Ordenar militares disponíveis:
            # 1. Primeiro por data do último serviço (mais antigo primeiro)
            # 2. Em caso de empate, por posto
            # 3. Em caso de empate no posto, por NIM
            militares_disponiveis.sort(key=lambda x: (
                x['ultimo_servico'],
                x['posto'],
                x['nim']
            ))

            # Nomear militares para esta escala
            total_necessario = servico.n_elementos + servico.n_reservas
            for i in range(min(total_necessario, len(militares_disponiveis))):
                militar_info = militares_disponiveis[i]
                militar = militar_info['militar']
                
                # Criar a nomeação
                EscalaMilitar.objects.create(
                    escala=escala,
                    militar=militar,
                    ordem_semana=i + 1 if not e_escala_b else None,
                    ordem_fds=i + 1 if e_escala_b else None,
                    e_reserva=i >= servico.n_elementos  # É reserva se já nomeamos todos os efetivos
                )
                
                # Atualizar a última data de nomeação no dicionário
                ultimas_nomeacoes[militar.nim] = data_atual

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