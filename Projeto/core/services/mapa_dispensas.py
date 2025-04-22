from datetime import date, timedelta
from typing import List, Dict, Tuple
from django.db.models import Q
from ..models import Militar, Dispensa, Nomeacao, Escala, Servico, Feriado
from ..utils import obter_feriados

class MapaDispensasService:
    def __init__(self, servico: Servico):
        self.servico = servico

    def obter_dispensas_periodo(self, data_inicio: date, data_fim: date) -> Dict[date, List[Tuple[Militar, str]]]:
        """
        Retorna um dicionário com as dispensas por data no formato:
        {
            data: [(militar, motivo), ...]
        }
        """
        dispensas = {}
        data_atual = data_inicio
        
        while data_atual <= data_fim:
            # Obter dispensas do dia
            dispensas_dia = Dispensa.objects.filter(
                data_inicio__lte=data_atual,
                data_fim__gte=data_atual,
                militar__in=self.servico.militares.all()
            ).select_related('militar')
            
            if dispensas_dia.exists():
                dispensas[data_atual] = [
                    (dispensa.militar, dispensa.motivo)
                    for dispensa in dispensas_dia
                ]
            
            data_atual += timedelta(days=1)
        
        return dispensas

    def obter_nomeacoes_periodo(self, data_inicio: date, data_fim: date) -> Dict[date, List[Tuple[Militar, str]]]:
        """
        Retorna um dicionário com as nomeações por data no formato:
        {
            data: [(militar, posicao), ...]
        }
        """
        nomeacoes = {}
        data_atual = data_inicio
        
        while data_atual <= data_fim:
            # Obter nomeações do dia
            nomeacoes_dia = Nomeacao.objects.filter(
                data=data_atual,
                escala__servico=self.servico
            ).select_related('militar', 'escala')
            
            if nomeacoes_dia.exists():
                nomeacoes[data_atual] = [
                    (nomeacao.militar, nomeacao.posicao)
                    for nomeacao in nomeacoes_dia
                ]
            
            data_atual += timedelta(days=1)
        
        return nomeacoes

    def obter_dias_uteis_periodo(self, data_inicio: date, data_fim: date) -> List[date]:
        """
        Retorna uma lista com os dias úteis no período
        """
        feriados = obter_feriados(data_inicio, data_fim)
        dias_uteis = []
        data_atual = data_inicio
        
        while data_atual <= data_fim:
            if data_atual.weekday() < 5 and data_atual not in feriados:
                dias_uteis.append(data_atual)
            data_atual += timedelta(days=1)
        
        return dias_uteis

    def obter_dias_fds_periodo(self, data_inicio: date, data_fim: date) -> List[date]:
        """
        Retorna uma lista com os fins de semana e feriados no período
        """
        feriados = obter_feriados(data_inicio, data_fim)
        dias_fds = []
        data_atual = data_inicio
        
        while data_atual <= data_fim:
            if data_atual.weekday() >= 5 or data_atual in feriados:
                dias_fds.append(data_atual)
            data_atual += timedelta(days=1)
        
        return dias_fds

    def gerar_mapa_dispensas(self, data_inicio: date, data_fim: date) -> Dict:
        """
        Gera o mapa completo de dispensas com todas as informações necessárias
        """
        return {
            'dispensas': self.obter_dispensas_periodo(data_inicio, data_fim),
            'nomeacoes': self.obter_nomeacoes_periodo(data_inicio, data_fim),
            'dias_uteis': self.obter_dias_uteis_periodo(data_inicio, data_fim),
            'dias_fds': self.obter_dias_fds_periodo(data_inicio, data_fim),
            'militares': list(self.servico.militares.all().order_by('posto', 'nim')),
            'data_inicio': data_inicio,
            'data_fim': data_fim
        } 