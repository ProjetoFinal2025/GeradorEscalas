from datetime import datetime, timedelta
from django.db.models import Q
from ..models import Escala, Militar, Servico, Feriado, EscalaMilitar, Dispensa
from ..utils import obter_feriados
from .nomeacao_service import (
    encontrar_militar_disponivel,
    validar_nomeacao,
    verificar_conflitos
)

def gerar_escala_automatica(servico, data_inicio, data_fim):
    """
    Gera escalas automaticamente para um serviço no período especificado.
    """
    # Verifica se o serviço está ativo
    if not servico.ativo:
        return False, "O serviço não está ativo"

    # Verifica se existem militares no serviço
    militares = servico.get_militares_ativos()
    if not militares.exists():
        return False, "Não existem militares ativos no serviço"

    # Obtém feriados no período
    feriados = obter_feriados(data_inicio, data_fim)

    # Gera escalas para cada dia do período
    data_atual = data_inicio
    while data_atual <= data_fim:
        # Verifica se é fim de semana ou feriado
        e_fim_semana = data_atual.weekday() >= 5
        e_feriado = data_atual in feriados
        e_escala_b = e_fim_semana or e_feriado

        # Verifica se o serviço tem escala B
        if e_escala_b and not servico.tem_escala_b:
            data_atual += timedelta(days=1)
            continue

        # Cria ou obtém a escala
        escala, created = Escala.objects.get_or_create(
            servico=servico,
            data=data_atual,
            e_escala_b=e_escala_b
        )

        # Atribui militares à escala
        for posicao in ['efetivo', 'reserva']:
            # Encontra militar disponível usando a função do nomeacao_service
            militar = encontrar_militar_disponivel(
                servico=servico,
                data=data_atual,
                e_escala_b=e_escala_b,
                posicao=posicao
            )

            if militar:
                # Cria nomeação usando EscalaMilitar
                ordem = calcular_ordem_militar(militar, servico, data_atual, e_escala_b)
                nomeacao = EscalaMilitar.objects.create(
                    escala=escala,
                    militar=militar,
                    ordem_semana=ordem if not e_escala_b else None,
                    ordem_fds=ordem if e_escala_b else None
                )

                # Valida a nomeação
                valido, mensagem = validar_nomeacao(nomeacao)
                if not valido:
                    nomeacao.delete()
                    return False, f"Erro ao nomear militar: {mensagem}"

        data_atual += timedelta(days=1)

    return True, "Escalas geradas com sucesso"

def calcular_ordem_militar(militar, servico, data, e_escala_b):
    """
    Calcula a ordem do militar na escala baseado em critérios específicos.
    """
    # Obtém a última escala do militar no mesmo tipo (semana ou fim de semana)
    ultima_escala = EscalaMilitar.objects.filter(
        militar=militar,
        escala__servico=servico,
        escala__e_escala_b=e_escala_b,
        escala__data__lt=data
    ).order_by('-escala__data').first()

    if ultima_escala:
        # Se é fim de semana, usa ordem_fds, senão usa ordem_semana
        ordem_atual = ultima_escala.ordem_fds if e_escala_b else ultima_escala.ordem_semana
        return ordem_atual + 1 if ordem_atual else 1
    return 1

def validar_escala(escala):
    """
    Valida uma escala, verificando se atende a todos os requisitos.
    """
    # Verifica se tem o número correto de militares
    nomeacoes = EscalaMilitar.objects.filter(escala=escala)
    if len(nomeacoes) != escala.servico.n_elementos:
        return False, f"Escala deve ter {escala.servico.n_elementos} militares"

    # Verifica se tem militar efetivo
    if not nomeacoes.filter(militar__posto__in=['COR', 'TCOR', 'MAJ', 'CAP']).exists():
        return False, "Escala deve ter um militar efetivo"

    # Verifica se tem militar reserva (se necessário)
    if escala.servico.n_elementos > 1 and not nomeacoes.filter(militar__posto__in=['TEN', 'ALF', 'ASP']).exists():
        return False, "Escala deve ter um militar reserva"

    # Verifica conflitos usando a função do nomeacao_service
    valido, mensagem = verificar_conflitos(escala)
    if not valido:
        return False, mensagem

    return True, "Escala válida" 