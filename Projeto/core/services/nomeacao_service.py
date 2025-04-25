from datetime import date, timedelta
from typing import Tuple, List, Optional
from django.db.models import QuerySet, Q
from operator import attrgetter
from django.utils import timezone

from ..models import Militar, Dispensa, Escala, Servico, POSTOS_CHOICES, EscalaMilitar, Feriado
from ..utils import obter_feriados

class NomeacaoService:
    def __init__(self, servico: Servico):
        self.servico = servico

    def calcular_tempo_sem_servico(self, militar: Militar, data: date) -> int:
        """
        Calcula quantos dias o militar está sem serviço
        Retorna um número grande se nunca teve serviço
        """
        ultimo_servico = EscalaMilitar.objects.filter(
            militar=militar,
            data__lt=data
        ).order_by('-data').first()

        if not ultimo_servico:
            return 9999  # Nunca teve serviço

        return (data - ultimo_servico.data).days

    def militar_disponivel(
        self, 
        militar: Militar, 
        data: date, 
        e_escala_b: bool = False,
        e_reserva: bool = False,
        regras_flexiveis: bool = False
    ) -> bool:
        # Verificar se já existe uma nomeação para este militar nesta data
        if EscalaMilitar.objects.filter(militar=militar, data=data).exists():
            return False

        # Verificar dispensas e licenças
        if Dispensa.objects.filter(
            militar=militar,
            data_inicio__lte=data,
            data_fim__gte=data
        ).exists():
            return False

        # Verificar dia antes de licença e dia de apresentação
        dispensas = Dispensa.objects.filter(militar=militar)
        for dispensa in dispensas:
            if (
                # Dia útil antes da licença
                (data.weekday() < 5 and data == dispensa.data_inicio - timedelta(days=1)) or
                # Dia de apresentação
                (data == dispensa.data_fim + timedelta(days=1))
            ):
                return False

        if not regras_flexiveis:
            # Verificar folga entre escalas (24h)
            if EscalaMilitar.objects.filter(
                militar=militar,
                data__in=[data - timedelta(days=1), data + timedelta(days=1)]
            ).exists():
                return False

            # Verificar folga na mesma escala (48h)
            if EscalaMilitar.objects.filter(
                militar=militar,
                data__in=[
                    data - timedelta(days=2),
                    data - timedelta(days=1),
                    data + timedelta(days=1),
                    data + timedelta(days=2)
                ],
                escala__e_escala_b=e_escala_b
            ).exists():
                return False

        return True

    def obter_proximo_militar(
        self, 
        data, 
        e_escala_b=False,
        e_reserva=False,
        militares_indisponiveis=None
    ):
        """
        Obtém o próximo militar disponível para nomeação, ordenando por tempo sem serviço
        """
        # Obtém todos os militares do serviço
        militares = self.servico.militares.filter(ativo=True)
        
        # Filtra militares que já estão nomeados como efetivos no mesmo dia
        militares_nomeados = EscalaMilitar.objects.filter(
            data=data,
            posicao='efetivo'
        ).values_list('militar__nim', flat=True)
        
        # Adiciona militares indisponíveis à lista de exclusão
        if militares_indisponiveis:
            militares_nomeados = list(militares_nomeados) + [m.nim for m in militares_indisponiveis]
        
        # Filtra militares disponíveis
        militares_disponiveis = [
            m for m in militares 
            if m.nim not in militares_nomeados and m.esta_disponivel(data)
        ]
        
        if not militares_disponiveis:
            return None

        # Ordena por tempo sem serviço (maior tempo primeiro)
        militares_disponiveis.sort(
            key=lambda m: self.calcular_tempo_sem_servico(m, data),
            reverse=True
        )

        # Se for reserva, pega o próximo na ordem
        if e_reserva and len(militares_disponiveis) > 1:
            return militares_disponiveis[1]  # Segundo da lista (próximo na ordem)
        
        return militares_disponiveis[0]  # Primeiro da lista

    def criar_nomeacao(
        self,
        militar: Militar,
        escala: Escala,
        data: date,
        posicao: str
    ) -> EscalaMilitar:
        # Verifica se já existe uma nomeação para este militar nesta data
        nomeacao_existente = EscalaMilitar.objects.filter(
            militar=militar,
            data=data
        ).first()

        if nomeacao_existente:
            # Se já existe, atualiza a posição se necessário
            if nomeacao_existente.posicao != posicao:
                nomeacao_existente.posicao = posicao
                nomeacao_existente.save()
            return nomeacao_existente

        # Se não existe, cria uma nova
        nomeacao = EscalaMilitar.objects.create(
            militar=militar,
            escala=escala,
            data=data,
            posicao=posicao
        )
        
        return nomeacao

    def gerar_nomeacoes_periodo(
        self,
        data_inicio: date,
        data_fim: date,
        militares: QuerySet[Militar]
    ) -> None:
        try:
            # Limpar nomeações existentes
            EscalaMilitar.objects.filter(
                data__gte=data_inicio,
                data__lte=data_fim,
                escala__servico=self.servico
            ).delete()

            Escala.objects.filter(
                servico=self.servico,
                data__gte=data_inicio,
                data__lte=data_fim
            ).delete()

        except Exception as e:
            raise

        feriados = obter_feriados(data_inicio, data_fim)

        # 1. Primeiro processar fins de semana e feriados (escala B)
        datas_fds = []
        data_atual = data_inicio
        while data_atual <= data_fim:
            e_fim_semana = data_atual.weekday() >= 5
            e_feriado = data_atual in feriados
            
            if e_fim_semana or e_feriado:
                datas_fds.append(data_atual)
            
            data_atual += timedelta(days=1)

        self._processar_datas(sorted(datas_fds), list(militares), True)

        # 2. Depois processar dias úteis (escala A)
        datas_uteis = []
        data_atual = data_inicio
        while data_atual <= data_fim:
            e_fim_semana = data_atual.weekday() >= 5
            e_feriado = data_atual in feriados
            
            if not (e_fim_semana or e_feriado):
                datas_uteis.append(data_atual)
            
            data_atual += timedelta(days=1)

        self._processar_datas(datas_uteis, list(militares), False)

        # 3. Resolver conflitos entre escalas (ajustando escala A)
        self._resolver_conflitos_folgas(data_inicio, data_fim, list(militares))

    def _processar_datas(self, datas: List[date], militares: List[Militar], e_escala_b: bool) -> None:
        # Ordenar as datas para garantir processamento sequencial
        datas.sort()
        
        # Ordenar militares por posto e antiguidade
        POSTOS_ORDEM = {posto: idx for idx, (posto, _) in enumerate(POSTOS_CHOICES)}
        militares_por_posto = {}
        for militar in militares:
            if militar.posto not in militares_por_posto:
                militares_por_posto[militar.posto] = []
            militares_por_posto[militar.posto].append(militar)

        # Ordena cada grupo de posto por NIM (mais antigos primeiro)
        for posto in militares_por_posto:
            militares_por_posto[posto].sort(key=lambda m: int(m.nim))

        # Reconstruir lista ordenada
        militares_ordenados = []
        for posto in sorted(militares_por_posto.keys(), key=lambda p: POSTOS_ORDEM.get(p, 0)):
            militares_ordenados.extend(militares_por_posto[posto])

        # Inicializar índice do militar atual
        indice_militar_atual = 0
        
        for data in datas:
            escala = Escala.objects.filter(servico=self.servico, data=data).first()
            if not escala:
                escala = Escala.objects.create(
                    servico=self.servico,
                    data=data,
                    e_escala_b=e_escala_b
                )

            # Encontrar próximo militar efetivo disponível
            militar_efetivo = None
            tentativas = 0
            while tentativas < len(militares_ordenados):
                militar = militares_ordenados[indice_militar_atual]
                
                # Verificar se o militar está disponível
                if militar.esta_disponivel(data):
                    # Se for escala A, verificar se o militar não está nomeado na escala B do dia anterior
                    if not e_escala_b:
                        data_anterior = data - timedelta(days=1)
                        nomeacao_anterior = EscalaMilitar.objects.filter(
                            militar=militar,
                            data=data_anterior,
                            escala__e_escala_b=True
                        ).exists()
                        if not nomeacao_anterior:
                            militar_efetivo = militar
                            break
                    else:
                        militar_efetivo = militar
                        break
                
                indice_militar_atual = (indice_militar_atual + 1) % len(militares_ordenados)
                tentativas += 1

            if militar_efetivo:
                self.criar_nomeacao(militar_efetivo, escala, data, 'efetivo')
                
                # Encontrar próximo militar reserva disponível
                militar_reserva = None
                indice_reserva = (indice_militar_atual + 1) % len(militares_ordenados)
                tentativas = 0
                while tentativas < len(militares_ordenados):
                    militar = militares_ordenados[indice_reserva]
                    if militar != militar_efetivo and militar.esta_disponivel(data):
                        # Se for escala A, verificar se o militar não está nomeado na escala B do dia anterior
                        if not e_escala_b:
                            data_anterior = data - timedelta(days=1)
                            nomeacao_anterior = EscalaMilitar.objects.filter(
                                militar=militar,
                                data=data_anterior,
                                escala__e_escala_b=True
                            ).exists()
                            if not nomeacao_anterior:
                                militar_reserva = militar
                                break
                        else:
                            militar_reserva = militar
                            break
                    indice_reserva = (indice_reserva + 1) % len(militares_ordenados)
                    tentativas += 1

                if militar_reserva:
                    self.criar_nomeacao(militar_reserva, escala, data, 'reserva')
                
                # Avançar para o próximo militar na lista
                indice_militar_atual = (indice_militar_atual + 1) % len(militares_ordenados)

    def _resolver_conflitos_folgas(self, data_inicio: date, data_fim: date, militares: List[Militar]) -> None:
        """
        Resolve conflitos de folgas entre as escalas A e B, ajustando a escala A.
        """
        data_atual = data_inicio
        while data_atual <= data_fim:
            if data_atual < data_fim:
                # Verificar nomeações no dia atual e no dia seguinte
                nomeacoes_hoje = EscalaMilitar.objects.filter(
                    data=data_atual,
                    escala__servico=self.servico,
                    escala__e_escala_b=False  # Apenas escala A
                ).select_related('escala', 'militar')

                nomeacoes_amanha = EscalaMilitar.objects.filter(
                    data=data_atual + timedelta(days=1),
                    escala__servico=self.servico
                ).select_related('escala', 'militar')

                # Verificar conflitos
                for nomeacao_hoje in nomeacoes_hoje:
                    for nomeacao_amanha in nomeacoes_amanha:
                        if nomeacao_hoje.militar == nomeacao_amanha.militar:
                            # Tentar encontrar substituto para a nomeação de hoje
                            militares_indisponiveis = [
                                n.militar for n in nomeacoes_hoje if n != nomeacao_hoje
                            ]
                            substituto = self.obter_proximo_militar(
                                nomeacao_hoje.data,
                                False,  # escala A
                                nomeacao_hoje.posicao == 'reserva',
                                militares_indisponiveis
                            )
                            
                            if substituto:
                                # Criar nova nomeação com o substituto
                                self.criar_nomeacao(
                                    substituto,
                                    nomeacao_hoje.escala,
                                    nomeacao_hoje.data,
                                    nomeacao_hoje.posicao
                                )
                                # Deletar nomeação antiga
                                nomeacao_hoje.delete()
                                
                                # Tentar nomear o militar original no próximo dia disponível
                                proxima_data = data_atual + timedelta(days=2)
                                while proxima_data <= data_fim:
                                    if self.militar_disponivel(
                                        nomeacao_hoje.militar,
                                        proxima_data,
                                        False,  # escala A
                                        nomeacao_hoje.posicao == 'reserva'
                                    ):
                                        escala_futura = Escala.objects.filter(
                                            servico=self.servico,
                                            data=proxima_data,
                                            e_escala_b=False
                                        ).first()
                                        if escala_futura:
                                            self.criar_nomeacao(
                                                nomeacao_hoje.militar,
                                                escala_futura,
                                                proxima_data,
                                                nomeacao_hoje.posicao
                                            )
                                            break
                                    proxima_data += timedelta(days=1)

            data_atual += timedelta(days=1)

    def obter_militares_disponiveis(self, data: date) -> list:
        """
        Retorna uma lista de militares disponíveis para nomeação em uma determinada data
        """
        # Obtém todos os militares ativos
        militares = Militar.objects.filter(ativo=True)
        
        # Filtra militares que já estão nomeados para a data
        militares_nomeados = EscalaMilitar.objects.filter(
            data=data
        ).values_list('militar__nim', flat=True)
        
        # Filtra militares com dispensas na data
        militares_com_dispensa = Dispensa.objects.filter(
            data_inicio__lte=data,
            data_fim__gte=data
        ).values_list('militar__nim', flat=True)
        
        # Filtra militares disponíveis
        militares_disponiveis = militares.exclude(
            Q(nim__in=militares_nomeados) |
            Q(nim__in=militares_com_dispensa)
        )
        
        return list(militares_disponiveis)
    
    def criar_nomeacao(self, militar: Militar, servico: Servico, data: date, posicao: str) -> bool:
        """
        Cria uma nomeação para um militar em um serviço específico
        """
        try:
            # Verifica se o militar já está nomeado para a data
            if EscalaMilitar.objects.filter(militar=militar, data=data).exists():
                return False
            
            # Verifica se o militar tem dispensa na data
            if Dispensa.objects.filter(
                militar=militar,
                data_inicio__lte=data,
                data_fim__gte=data
            ).exists():
                return False
            
            # Cria a nomeação
            EscalaMilitar.objects.create(
                militar=militar,
                servico=servico,
                data=data,
                posicao=posicao,
                data_criacao=timezone.now()
            )
            
            return True
        except Exception:
            return False
    
    def remover_nomeacao(self, militar: Militar, data: date) -> bool:
        """
        Remove uma nomeação de um militar em uma data específica
        """
        try:
            nomeacao = EscalaMilitar.objects.get(militar=militar, data=data)
            nomeacao.delete()
            return True
        except EscalaMilitar.DoesNotExist:
            return False
