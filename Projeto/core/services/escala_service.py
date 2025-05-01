from datetime import datetime, date, timedelta
from typing import Tuple, List, Optional, Dict
from django.db.models import QuerySet, Q
from django.utils import timezone

from ..models import Escala, Militar, Servico, Feriado, EscalaMilitar, Dispensa
from ..utils import obter_feriados

class EscalaService:
    """Serviço para gerir escalas e nomeações militares."""
    
    @staticmethod
    def verificar_periodo(data_inicio: date, data_fim: date) -> Tuple[bool, str]:
        """Verifica se o período para nomeações é válido."""
        hoje = timezone.now().date()

        if data_inicio > data_fim:
            return False, "A data inicial não pode ser posterior à data final"

        if data_inicio < hoje:
            return False, "A data inicial não pode ser no passado"

        dias_intervalo = (data_fim - data_inicio).days
        if dias_intervalo > 60:
            return False, "O intervalo máximo para nomeações é de 60 dias"

        return True, "Período válido"

    @staticmethod
    def obter_dias_escala(data_inicio: date, data_fim: date) -> Dict[str, List[date]]:
        """Obtém as datas separadas por tipo de escala (dias úteis e fins de semana/feriados)."""
        dias = {
            'escala_a': [],
            'escala_b': []
        }
        
        # Verifica se o período é válido
        valido, mensagem = EscalaService.verificar_periodo(data_inicio, data_fim)
        if not valido:
            return dias

        # Obter todos os feriados
        feriados = Feriado.objects.filter(
            data__gte=data_inicio,
            data__lte=data_fim
        ).values_list('data', flat=True)

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
    def verificar_disponibilidade_militar(militar: Militar, data: date) -> Tuple[bool, str]:
        """Verifica se um militar está disponível para uma data específica."""
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
            data_inicio=data + timedelta(days=1)
        ).first()

        if licenca:
            return False, "Militar entra de licença no dia seguinte"

        licenca = Dispensa.objects.filter(
            militar=militar,
            data_fim=data - timedelta(days=1)
        ).first()

        if licenca:
            return False, "Militar apresentou-se de licença no dia anterior"

        return True, "Militar disponível"

    @staticmethod
    def nomear_escala(servico: Servico, data: date) -> Tuple[bool, str]:
        """Nomeia um efetivo e um reserva para um dia específico."""
        # Verifica se o serviço está ativo
        if not servico.ativo:
            return False, "O serviço não está ativo"

        # Obtém militares do serviço
        militares = servico.militares.all()
        if not militares.exists():
            return False, "Não existem militares no serviço"

        # Filtra militares disponíveis
        militares_disponiveis = []
        for militar in militares:
            disponivel, _ = EscalaService.verificar_disponibilidade_militar(militar, data)
            if disponivel:
                militares_disponiveis.append(militar)

        if len(militares_disponiveis) < 2:
            return False, "Não existem militares suficientes disponíveis"

        # Cria ou obtém a escala
        escala, _ = Escala.objects.get_or_create(
            servico=servico,
            data=data,
            e_escala_b=data.weekday() >= 5 or data in Feriado.objects.all()
        )

        # Nomeia efetivo
        efetivo = militares_disponiveis[0]
        EscalaMilitar.objects.create(
            escala=escala,
            militar=efetivo,
            posicao='efetivo'
        )

        # Nomeia reserva
        reserva = militares_disponiveis[1]
        EscalaMilitar.objects.create(
            escala=escala,
            militar=reserva,
            posicao='reserva'
        )

        return True, "Escala nomeada com sucesso"