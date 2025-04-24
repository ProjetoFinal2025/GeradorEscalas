from datetime import date, timedelta
from django.db.models import Q
from ..models import Escala, Militar, Servico, Feriado, EscalaMilitar, Dispensa
from ..utils import obter_feriados
from .nomeacao_service import (
    encontrar_militar_disponivel,
    validar_nomeacao,
    verificar_conflitos
)

def gerar_previsao_escalas(servico, data_inicio, data_fim):
    """
    Gera uma previsão de escalas para um determinado serviço e período.
    
    Args:
        servico: Objeto Servico para o qual gerar a previsão
        data_inicio: Data de início do período
        data_fim: Data de fim do período
        
    Returns:
        Lista de dicionários contendo informações sobre cada dia do período
    """
    # Obter feriados no período
    feriados = obter_feriados(data_inicio, data_fim)
    
    # Gerar lista de datas com suas escalas
    datas = []
    data_atual = data_inicio

    while data_atual <= data_fim:
        # Verificar se é fim de semana ou feriado
        e_fim_semana = data_atual.weekday() >= 5
        e_feriado = data_atual in feriados
        e_escala_b = e_fim_semana or e_feriado

        # Buscar escala existente para esta data
        escala = Escala.objects.filter(
            servico=servico,
            data=data_atual,
            e_escala_b=e_escala_b
        ).first()

        # Se não existe escala, gerar previsão
        if not escala:
            escala = gerar_previsao_dia(servico, data_atual, e_escala_b)

        datas.append({
            'data': data_atual,
            'escala': escala,
            'e_fim_semana': e_fim_semana,
            'e_feriado': e_feriado,
            'tipo_dia': 'feriado' if e_feriado else ('fim_semana' if e_fim_semana else 'util')
        })
        
        data_atual += timedelta(days=1)

    return datas

def gerar_previsao_dia(servico, data, e_escala_b):
    """
    Gera uma previsão de escala para um dia específico.
    
    Args:
        servico: Objeto Servico
        data: Data para gerar a previsão
        e_escala_b: Se é escala B (fim de semana ou feriado)
        
    Returns:
        Objeto Escala com a previsão
    """
    # Verificar se o serviço tem escala B
    if e_escala_b and not servico.tem_escala_b:
        return None

    # Criar objeto de escala para previsão
    escala = Escala(
        servico=servico,
        data=data,
        e_escala_b=e_escala_b,
        prevista=True
    )
    escala.save()  # Salvar para poder criar as EscalaMilitar

    # Obter militares do serviço
    militares_servico = servico.militares.filter(ativo=True)
    if not militares_servico.exists():
        return escala

    # Encontrar militar efetivo disponível
    militar_efetivo = encontrar_militar_disponivel(
        servico=servico,
        data=data,
        e_escala_b=e_escala_b,
        posicao='efetivo'
    )

    if militar_efetivo:
        # Criar EscalaMilitar para o efetivo
        EscalaMilitar.objects.create(
            escala=escala,
            militar=militar_efetivo,
            ordem_semana=1 if not e_escala_b else None,
            ordem_fds=1 if e_escala_b else None
        )

    # Se o serviço precisa de reserva, encontrar militar reserva
    if servico.n_elementos > 1:
        militar_reserva = encontrar_militar_disponivel(
            servico=servico,
            data=data,
            e_escala_b=e_escala_b,
            posicao='reserva'
        )
        if militar_reserva:
            # Criar EscalaMilitar para o reserva
            EscalaMilitar.objects.create(
                escala=escala,
                militar=militar_reserva,
                ordem_semana=2 if not e_escala_b else None,
                ordem_fds=2 if e_escala_b else None
            )

    return escala

def obter_periodo_previsao(data_inicio_str=None, data_fim_str=None):
    """
    Obtém o período de previsão a partir das strings de data fornecidas.
    
    Args:
        data_inicio_str: String da data de início no formato YYYY-MM-DD
        data_fim_str: String da data de fim no formato YYYY-MM-DD
        
    Returns:
        Tupla com (data_inicio, data_fim) como objetos date
    """
    hoje = date.today()
    
    try:
        data_inicio = date.fromisoformat(data_inicio_str) if data_inicio_str else hoje
        data_fim = date.fromisoformat(data_fim_str) if data_fim_str else hoje + timedelta(days=30)
    except ValueError:
        data_inicio = hoje
        data_fim = hoje + timedelta(days=30)
        
    return data_inicio, data_fim

def obter_servico_previsao(servico_id):
    """
    Obtém o serviço para o qual gerar a previsão.
    
    Args:
        servico_id: ID do serviço
        
    Returns:
        Objeto Servico ou None se não encontrado
    """
    if servico_id:
        try:
            return Servico.objects.get(id=servico_id)
        except Servico.DoesNotExist:
            return None
    return Servico.objects.filter(ativo=True).first()

def gerar_previsao_escalas_a_b(servico, data_inicio, data_fim):
    """
    Gera previsão de escalas A e B para um serviço no período especificado.
    Retorna um dicionário com as escalas previstas.
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

    # Estrutura para armazenar as previsões
    previsoes = {
        'escala_a': [],
        'escala_b': []
    }

    # Gera previsões para cada dia do período
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

        # Cria objeto de previsão para o dia
        previsao_dia = {
            'data': data_atual,
            'e_escala_b': e_escala_b,
            'militares': []
        }

        # Atribui militares à previsão
        for posicao in ['efetivo', 'reserva']:
            # Encontra militar disponível
            militar = encontrar_militar_disponivel(
                servico=servico,
                data=data_atual,
                e_escala_b=e_escala_b,
                posicao=posicao
            )

            if militar:
                # Calcula ordem do militar
                ordem = calcular_ordem_militar(militar, servico, data_atual, e_escala_b)
                
                # Adiciona militar à previsão
                previsao_dia['militares'].append({
                    'militar': militar,
                    'posicao': posicao,
                    'ordem': ordem
                })

        # Adiciona previsão ao grupo correto
        if e_escala_b:
            previsoes['escala_b'].append(previsao_dia)
        else:
            previsoes['escala_a'].append(previsao_dia)

        data_atual += timedelta(days=1)

    return True, previsoes

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

def validar_previsao(previsao):
    """
    Valida uma previsão de escala.
    """
    # Verifica se tem o número correto de militares
    if len(previsao['militares']) != previsao['servico'].n_elementos:
        return False, f"Escala deve ter {previsao['servico'].n_elementos} militares"

    # Verifica se tem militar efetivo
    if not any(m['militar'].posto in ['COR', 'TCOR', 'MAJ', 'CAP'] for m in previsao['militares']):
        return False, "Escala deve ter um militar efetivo"

    # Verifica se tem militar reserva (se necessário)
    if previsao['servico'].n_elementos > 1 and not any(m['militar'].posto in ['TEN', 'ALF', 'ASP'] for m in previsao['militares']):
        return False, "Escala deve ter um militar reserva"

    # Verifica conflitos
    for militar_info in previsao['militares']:
        # Cria uma escala temporária para validação
        escala_temp = Escala(
            servico=previsao['servico'],
            data=previsao['data'],
            e_escala_b=previsao['e_escala_b']
        )
        
        # Cria uma nomeação temporária
        nomeacao_temp = EscalaMilitar(
            escala=escala_temp,
            militar=militar_info['militar']
        )

        # Valida a nomeação
        valido, mensagem = validar_nomeacao(nomeacao_temp)
        if not valido:
            return False, f"Erro ao nomear militar: {mensagem}"

    return True, "Previsão válida"

def aplicar_previsao(previsoes):
    """
    Aplica as previsões geradas, criando as escalas e nomeações reais.
    """
    for tipo_escala in ['escala_a', 'escala_b']:
        for previsao in previsoes[tipo_escala]:
            # Cria a escala
            escala = Escala.objects.create(
                servico=previsao['servico'],
                data=previsao['data'],
                e_escala_b=previsao['e_escala_b']
            )

            # Cria as nomeações
            for militar_info in previsao['militares']:
                EscalaMilitar.objects.create(
                    escala=escala,
                    militar=militar_info['militar'],
                    ordem_semana=militar_info['ordem'] if not previsao['e_escala_b'] else None,
                    ordem_fds=militar_info['ordem'] if previsao['e_escala_b'] else None
                )

    return True, "Previsões aplicadas com sucesso" 