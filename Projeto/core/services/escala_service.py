from datetime import datetime, date, timedelta
from typing import Tuple, List, Optional, Dict
from django.db.models import QuerySet, Q
from django.utils import timezone

from ..models import Escala, Militar, Servico, Feriado, EscalaMilitar, Dispensa
from ..utils import obter_feriados

class EscalaService:
    """
    Serviço responsável por gerir escalas e nomeações.
    Inclui funcionalidades para gerar previsões, validar nomeações e gerir ordens de entrada.
    """
    
    @staticmethod
    def listar_militares_servico(servico: Servico) -> QuerySet[Militar]:
        """
        Lista todos os militares atribuídos a um determinado serviço.
        """
        return servico.militares.all()

    @staticmethod
    def verificar_dias_previsao(data_inicio: date, data_fim: date) -> Tuple[bool, str]:
        """
        Verifica se o intervalo de datas para previsão é válido.
        """
        hoje = timezone.now().date()

        if data_inicio > data_fim:
            return False, "A data inicial não pode ser posterior à data final"

        if data_inicio < hoje:
            return False, "A data inicial não pode ser no passado"

        dias_intervalo = (data_fim - data_inicio).days
        if dias_intervalo > 60:
            return False, "O intervalo máximo para previsão é de 60 dias"

        return True, "Intervalo de datas válido"

    @staticmethod
    def verificar_disponibilidade_militar(militar: Militar, data: date) -> Tuple[bool, str]:
        """
        Verifica se um militar está disponível para ser nomeado numa determinada data.
        """
        # Verifica dispensas
        dispensa = Dispensa.objects.filter(
            militar=militar,
            data_inicio__lte=data,
            data_fim__gte=data
        ).first()

        if dispensa:
            return False, f"Militar em dispensa: {dispensa.motivo}"

        # Verifica se já tem escala neste dia
        escala_existente = EscalaMilitar.objects.filter(
            militar=militar,
            escala__data=data
        ).exists()

        if escala_existente:
            return False, "Militar já tem escala neste dia"

        # Verifica dia antes e dia da apresentação de licença
        licenca = Dispensa.objects.filter(
            militar=militar,
            data_inicio=data + timedelta(days=1)  # Dia seguinte
        ).first()

        if licenca:
            return False, "Militar entra de licença no dia seguinte"

        licenca = Dispensa.objects.filter(
            militar=militar,
            data_fim=data - timedelta(days=1)  # Dia anterior
        ).first()

        if licenca:
            return False, "Militar apresentou-se de licença no dia anterior"

        return True, "Militar disponível"
    
    @staticmethod
    def filtrar_militares_disponiveis(militares: QuerySet[Militar], data: date) -> QuerySet[Militar]:
        """
        Filtra uma lista de militares removendo os que estão indisponíveis na data especificada.
        """
        return militares.exclude(
            Q(dispensas__data_inicio__lte=data, dispensas__data_fim__gte=data) |
            Q(escalamilitar__escala__data=data)
        )
    
    @staticmethod
    def calcular_ordem_militar(militar: Militar, servico: Servico, data: date, e_escala_b: bool) -> Tuple[int, int]:
        """
        Calcula a ordem do militar na escala baseado em critérios específicos.
        Retorna uma tupla com (dias_sem_servico, ordem_entrada)
        """
        # Calcula dias desde o último serviço
        ultima_escala = EscalaMilitar.objects.filter(
            militar=militar,
            escala__servico=servico,
            escala__data__lt=data,
            escala__e_escala_b=e_escala_b
        ).order_by('-escala__data').first()

        dias_sem_servico = 999999 if not ultima_escala else (data - ultima_escala.escala.data).days

        # Obtém ordem de entrada
        ordem_entrada = 999999
        if ultima_escala:
            ordem_entrada = ultima_escala.ordem_fds if e_escala_b else ultima_escala.ordem_semana
            ordem_entrada = ordem_entrada + 1 if ordem_entrada else 1

        return dias_sem_servico, ordem_entrada

    @staticmethod
    def calcular_antiguidade(militar: Militar) -> Tuple[int, int]:
        """
        Calcula a antiguidade do militar.
        Retorna uma tupla com (ordem_posto, dias_posto)
        """
        # Ordem dos postos (maior = mais antigo)
        ordem_postos = {
            'COR': 10, 'TCOR': 9, 'MAJ': 8, 'CAP': 7,
            'TEN': 6, 'ALF': 5, 'ASP': 4
        }
        
        ordem_posto = ordem_postos.get(militar.posto, 0)
        dias_posto = (date.today() - militar.data_promocao).days if militar.data_promocao else 0
        
        return ordem_posto, dias_posto

    @staticmethod
    def verificar_folga_minima(militar: Militar, data: date, e_escala_b: bool) -> Tuple[bool, str]:
        """
        Verifica se o militar respeita a folga mínima.
        """
        # Obtém a última escala do mesmo tipo
        ultima_escala = EscalaMilitar.objects.filter(
            militar=militar,
            escala__e_escala_b=e_escala_b,
            escala__data__lt=data
        ).order_by('-escala__data').first()

        if not ultima_escala:
            return True, "Primeira nomeação"

        dias_folga = (data - ultima_escala.escala.data).days
        folga_minima = 2 if e_escala_b else 1  # 48h para mesma escala, 24h entre escalas

        if dias_folga < folga_minima:
            return False, f"Folga mínima não respeitada ({dias_folga} dias)"

        return True, "Folga mínima respeitada"

    @staticmethod
    def ordenar_militares(militares: list[Militar], servico: Servico, data: date, e_escala_b: bool) -> list[Militar]:
        """
        Ordena os militares considerando:
        1. Novos militares (prioridade máxima)
        2. Dias desde o último serviço (mais dias = maior prioridade)
        3. Ordem do posto (maior = mais antigo)
        4. Antiguidade no posto (mais dias = mais antigo)
        
        Para escala B (fins de semana/feriados), prioriza militares com mais dias sem serviço
        """
        # Cria lista de tuplos (militar, info)
        militares_info = []
        for militar in militares:
            # Verifica se é novo
            e_novo = not EscalaMilitar.objects.filter(militar=militar).exists()
            
            # Calcula dias sem serviço
            dias_sem_servico, ordem = EscalaService.calcular_ordem_militar(militar, servico, data, e_escala_b)
            
            # Calcula antiguidade
            ordem_posto, dias_posto = EscalaService.calcular_antiguidade(militar)
            
            militares_info.append((
                militar,
                e_novo,
                dias_sem_servico,
                ordem_posto,
                dias_posto
            ))

        # Ordena por:
        # 1. Novos militares (primeiro)
        # 2. Dias sem serviço (decrescente)
        # 3. Ordem do posto (decrescente)
        # 4. Dias no posto (decrescente)
        if e_escala_b:
            # Para escala B, prioriza dias sem serviço
            militares_info.sort(key=lambda x: (-x[1], -x[2], -x[3], -x[4]))
        else:
            # Para escala A, mantém ordenação padrão
            militares_info.sort(key=lambda x: (-x[1], -x[2], -x[3], -x[4]))

        # Retorna apenas os militares ordenados
        return [m[0] for m in militares_info]

    @staticmethod
    def obter_dias_escala(data_inicio: date, data_fim: date) -> Dict[str, List[date]]:
        """
        Obtém as datas separadas por tipo de escala (dias úteis e fins de semana/feriados).
        """
        dias = {
            'escala_a': [],
            'escala_b': []
        }
        
        # Obter todos os feriados (nacionais, móveis e personalizados)
        feriados = obter_feriados(data_inicio, data_fim)

        data_atual = data_inicio
        while data_atual <= data_fim:
            e_fds = data_atual.weekday() >= 5
            e_feriado = data_atual in feriados
            
            if e_fds or e_feriado:
                dias['escala_b'].append(data_atual)
            else:
                dias['escala_a'].append(data_atual)
            
            data_atual += timedelta(days=1)

        return dias

    @staticmethod
    def gerar_escala(servico: Servico, data: date, e_escala_b: bool, e_previsao: bool = False) -> Tuple[bool, str]:
        """
        Gera uma escala para um dia específico.
        """
        # Verifica se o serviço está ativo
        if not servico.ativo:
            return False, "O serviço não está ativo"

        # Verifica se existem militares no serviço
        todos_militares = servico.get_militares_ativos()
        if not todos_militares.exists():
            return False, "Não existem militares ativos no serviço"

        # Filtra militares disponíveis para este tipo de escala
        militares_disponiveis = []
        for militar in todos_militares:
            # Verifica disponibilidade geral
            disponivel, _ = EscalaService.verificar_disponibilidade_militar(militar, data)
            if not disponivel:
                continue

            # Verifica folga mínima para este tipo de escala
            folga_minima, _ = EscalaService.verificar_folga_minima(militar, data, e_escala_b)
            if not folga_minima:
                continue

            # Verifica se o militar já tem escala neste dia
            tem_escala_no_dia = EscalaMilitar.objects.filter(
                militar=militar,
                escala__data=data
            ).exists()

            if not tem_escala_no_dia:
                militares_disponiveis.append(militar)

        if not militares_disponiveis:
            return False, "Não existem militares disponíveis para esta data"

        # Ordena militares considerando apenas escalas do mesmo tipo
        militares_ordenados = EscalaService.ordenar_militares(militares_disponiveis, servico, data, e_escala_b)

        # Cria ou obtém a escala
        escala, _ = Escala.objects.get_or_create(
            servico=servico,
            data=data,
            e_escala_b=e_escala_b,
            prevista=e_previsao
        )

        # Nomeia efetivo
        if militares_ordenados:
            efetivo = militares_ordenados[0]
            # Verifica se o militar já tem escala neste dia
            tem_escala_no_dia = EscalaMilitar.objects.filter(
                militar=efetivo,
                escala__data=data
            ).exists()

            if not tem_escala_no_dia:
                EscalaMilitar.objects.create(
                    escala=escala,
                    militar=efetivo,
                    posicao='efetivo',
                    ordem_semana=1 if not e_escala_b else None,
                    ordem_fds=1 if e_escala_b else None
                )

        # Nomeia reserva se necessário
        if servico.n_elementos > 1 and len(militares_ordenados) > 1:
            reserva = militares_ordenados[1]
            # Verifica se o militar já tem escala neste dia
            tem_escala_no_dia = EscalaMilitar.objects.filter(
                militar=reserva,
                escala__data=data
            ).exists()

            if not tem_escala_no_dia:
                EscalaMilitar.objects.create(
                    escala=escala,
                    militar=reserva,
                    posicao='reserva',
                    ordem_semana=2 if not e_escala_b else None,
                    ordem_fds=2 if e_escala_b else None
                )

        return True, "Escala gerada com sucesso"

    @staticmethod
    def validar_nomeacao(nomeacao: EscalaMilitar) -> Tuple[bool, str]:
        """
        Valida uma nomeação, verificando se atende a todos os requisitos.
        """
        # Verifica se o militar está disponível
        disponivel, mensagem = EscalaService.verificar_disponibilidade_militar(
            nomeacao.militar, 
            nomeacao.escala.data
        )
        if not disponivel:
            return False, mensagem

        # Verifica se a escala tem o número correto de militares
        n_militares = nomeacao.escala.militares_info.count()
        if n_militares > nomeacao.escala.servico.n_elementos:
            return False, f"Escala já tem o número máximo de militares ({nomeacao.escala.servico.n_elementos})"

        # Verifica se já existe um militar na mesma posição
        if nomeacao.escala.militares_info.filter(posicao=nomeacao.posicao).exists():
            return False, f"Já existe um militar nomeado como {nomeacao.posicao}"

        return True, "Nomeação válida"

    @staticmethod
    def verificar_conflitos(escala: Escala) -> Tuple[bool, str]:
        """
        Verifica se existem conflitos em uma escala.
        """
        # Verifica se tem o número correto de militares
        n_militares = escala.militares_info.count()
        if n_militares != escala.servico.n_elementos:
            return False, f"Escala deve ter {escala.servico.n_elementos} militares"

        # Verifica se tem militar efetivo
        if not escala.militares_info.filter(posicao='efetivo').exists():
            return False, "Escala deve ter um militar efetivo"

        # Verifica se tem militar reserva (se necessário)
        if escala.servico.n_elementos > 1 and not escala.militares_info.filter(posicao='reserva').exists():
            return False, "Escala deve ter um militar reserva"

        # Verifica folgas mínimas
        for nomeacao in escala.militares_info.all():
            folga_minima, mensagem = EscalaService.verificar_folga_minima(
                nomeacao.militar,
                escala.data,
                escala.e_escala_b
            )
            if not folga_minima:
                return False, f"Conflito de folga: {mensagem}"

        return True, "Sem conflitos"

    @staticmethod
    def obter_ordem_entrada(militar: Militar, servico: Servico, e_escala_b: bool) -> int:
        """
        Obtém a ordem de entrada atual do militar.
        """
        ultima_escala = EscalaMilitar.objects.filter(
            militar=militar,
            escala__servico=servico,
            escala__e_escala_b=e_escala_b,
            ordem_fds__isnull=False if e_escala_b else Q(ordem_semana__isnull=False)
        ).order_by('-escala__data').first()

        if not ultima_escala:
            return 999999  # Se não tem ordem, coloca no fim

        return ultima_escala.ordem_fds if e_escala_b else ultima_escala.ordem_semana

    @staticmethod
    def obter_dias_fds_feriados(data_inicio: date, data_fim: date) -> List[date]:
        """
        Obtém uma lista com as datas que são fins de semana ou feriados num dado intervalo.
        """
        dias_especiais = []
        feriados = Feriado.objects.filter(
            data__gte=data_inicio,
            data__lte=data_fim
        ).values_list('data', flat=True)

        data_atual = data_inicio
        while data_atual <= data_fim:
            e_fds = data_atual.weekday() >= 5
            e_feriado = data_atual in feriados
            
            if e_fds or e_feriado:
                dias_especiais.append(data_atual)
            
            data_atual += timedelta(days=1)

        return dias_especiais
    
    @staticmethod
    def obter_dias_semana(data_inicio: date, data_fim: date) -> List[date]:
        """
        Obtém uma lista com as datas que são dias de semana (excluindo fins de semana e feriados).
        """
        dias_semana = []
        feriados = Feriado.objects.filter(
            data__gte=data_inicio,
            data__lte=data_fim
        ).values_list('data', flat=True)

        data_atual = data_inicio
        while data_atual <= data_fim:
            e_dia_semana = data_atual.weekday() < 5
            nao_e_feriado = data_atual not in feriados
            
            if e_dia_semana and nao_e_feriado:
                dias_semana.append(data_atual)

            data_atual += timedelta(days=1)
            
        return dias_semana

    @staticmethod
    def gerar_escala_automatica(servico: Servico, data_inicio: date, data_fim: date) -> Tuple[bool, str]:
        """
        Gera escalas automaticamente para um serviço no período especificado.
        Temporariamente gerando apenas escalas de fins de semana e feriados,
        sem manipulação da ordem dos militares.
        """
        # Verifica se o serviço está ativo
        if not servico.ativo:
            return False, "O serviço não está ativo"

        # Verifica se existem militares no serviço
        todos_militares = servico.get_militares_ativos()
        if not todos_militares.exists():
            return False, "Não existem militares ativos no serviço"

        # Verifica se o período é válido
        valido, mensagem = EscalaService.verificar_dias_previsao(data_inicio, data_fim)
        if not valido:
            return False, mensagem

        # Obtém todas as datas do período
        dias_fds_feriados = EscalaService.obter_dias_fds_feriados(data_inicio, data_fim)

        # Processa TODOS os fins de semana e feriados
        if servico.tem_escala_b and dias_fds_feriados:
            for data in dias_fds_feriados:
                # Filtra militares disponíveis
                militares_disponiveis = [
                    m for m in todos_militares 
                    if EscalaService.verificar_disponibilidade_militar(m, data)[0]
                ]

                if not militares_disponiveis:
                    continue

                escala, _ = Escala.objects.get_or_create(
                    servico=servico,
                    data=data,
                    e_escala_b=True
                )

                # Nomeia efetivo
                if militares_disponiveis:
                    EscalaMilitar.objects.create(
                        escala=escala,
                        militar=militares_disponiveis[0],
                        posicao='efetivo'
                    )

                # Nomeia reserva se necessário
                if servico.n_elementos > 1 and len(militares_disponiveis) > 1:
                    EscalaMilitar.objects.create(
                        escala=escala,
                        militar=militares_disponiveis[1],
                        posicao='reserva'
                    )

        return True, "Escalas de fins de semana e feriados geradas com sucesso"

    @staticmethod
    def gerar_previsao(servico: Servico, data_inicio: date, data_fim: date) -> List[Dict]:
        """
        Gera uma previsão de escalas para um determinado serviço e período.
        Processa primeiro as escalas B (fins de semana/feriados) e depois as escalas A (dias úteis).
        """
        # Separar dias por tipo ANTES de processar
        dias_escala = EscalaService.obter_dias_escala(data_inicio, data_fim)
        datas = []
        
        # Processar ESCALA B primeiro (fins de semana/feriados)
        for data in dias_escala['escala_b']:
            sucesso, _ = EscalaService.gerar_escala(servico, data, True, True)
            if sucesso:
                escala = Escala.objects.get(servico=servico, data=data, e_escala_b=True)
                datas.append({
                    'data': data,
                    'escala': escala,
                    'tipo_dia': 'feriado' if data in Feriado.objects.all() else 'fim_semana'
                })
        
        # Processar ESCALA A depois (dias úteis)
        for data in dias_escala['escala_a']:
            sucesso, _ = EscalaService.gerar_escala(servico, data, False, True)
            if sucesso:
                escala = Escala.objects.get(servico=servico, data=data, e_escala_b=False)
                datas.append({
                    'data': data,
                    'escala': escala,
                    'tipo_dia': 'util'
                })
        
        return sorted(datas, key=lambda x: x['data'])  # Ordenar por data final

    @staticmethod
    def aplicar_previsao(previsoes: Dict[str, List[Dict]]) -> Tuple[bool, str]:
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

    @staticmethod
    def obter_periodo_previsao(data_inicio_str: Optional[str] = None, data_fim_str: Optional[str] = None) -> Tuple[date, date]:
        """
        Obtém o período de previsão a partir das strings de data fornecidas.
        """
        hoje = date.today()
        
        try:
            data_inicio = date.fromisoformat(data_inicio_str) if data_inicio_str else hoje
            data_fim = date.fromisoformat(data_fim_str) if data_fim_str else hoje + timedelta(days=30)
        except ValueError:
            data_inicio = hoje
            data_fim = hoje + timedelta(days=30)
            
        return data_inicio, data_fim

    @staticmethod
    def obter_servico_previsao(servico_id: Optional[int] = None) -> Optional[Servico]:
        """
        Obtém o serviço para o qual gerar a previsão.
        """
        if servico_id:
            try:
                return Servico.objects.get(id=servico_id)
            except Servico.DoesNotExist:
                return None
        return Servico.objects.filter(ativo=True).first()

    @staticmethod
    def realizar_troca(escala: Escala, militar_efetivo: Militar, militar_reserva: Militar) -> Tuple[bool, str]:
        """
        Realiza uma troca de serviço entre o efetivo e o reserva.
        """
        # Verifica se os militares existem na escala
        efetivo = escala.militares_info.filter(
            militar=militar_efetivo,
            posicao='efetivo'
        ).first()
        
        reserva = escala.militares_info.filter(
            militar=militar_reserva,
            posicao='reserva'
        ).first()

        if not efetivo or not reserva:
            return False, "Militar(es) não encontrado(s) na escala"

        # Realiza a troca
        efetivo.posicao = 'reserva'
        efetivo.save()

        reserva.posicao = 'efetivo'
        reserva.save()

        return True, "Troca realizada com sucesso"

    @staticmethod
    def realizar_destroca(escala: Escala) -> Tuple[bool, str]:
        """
        Realiza a destroca na primeira oportunidade.
        """
        # Obtém o efetivo e reserva atuais
        efetivo = escala.militares_info.filter(posicao='efetivo').first()
        reserva = escala.militares_info.filter(posicao='reserva').first()

        if not efetivo or not reserva:
            return False, "Não existem militares para destroca"

        # Realiza a destroca
        efetivo.posicao = 'efetivo'
        efetivo.save()

        reserva.posicao = 'reserva'
        reserva.save()

        return True, "Destroca realizada com sucesso" 