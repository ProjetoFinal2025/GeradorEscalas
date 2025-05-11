from datetime import date, datetime
from typing import Tuple, Optional, List
from django.db import transaction
from django.utils import timezone
from ..models import Militar, Nomeacao, TrocaServico, EscalaMilitar, Servico
from .escala_service import EscalaService
from django.db import models

class TrocaService:
    @staticmethod
    def solicitar_troca(
        militar_solicitante: Militar,
        militar_trocado: Militar,
        data_troca: date
    ) -> Tuple[bool, str]:
        """
        Solicita uma troca de serviço entre dois militares.
        Retorna (sucesso, mensagem)
        """
        # Verificar se já existe uma troca pendente para esta data
        if TrocaServico.objects.filter(
            data_troca=data_troca,
            status='PENDENTE'
        ).exists():
            return False, "Já existe uma troca pendente para esta data"

        # Verificar se os militares estão nomeados para a data
        nomeacao_solicitante = Nomeacao.objects.filter(
            escala_militar__militar=militar_solicitante,
            data=data_troca
        ).first()

        nomeacao_trocado = Nomeacao.objects.filter(
            escala_militar__militar=militar_trocado,
            data=data_troca
        ).first()

        if not nomeacao_solicitante or not nomeacao_trocado:
            return False, "Um ou ambos os militares não estão nomeados para esta data"

        # Verificar se os militares pertencem ao mesmo serviço
        servico_solicitante = nomeacao_solicitante.escala_militar.escala.servico
        servico_trocado = nomeacao_trocado.escala_militar.escala.servico

        if servico_solicitante != servico_trocado:
            return False, "Os militares pertencem a serviços diferentes"

        # Criar a solicitação de troca
        troca = TrocaServico.objects.create(
            militar_solicitante=militar_solicitante,
            militar_trocado=militar_trocado,
            data_troca=data_troca
        )

        return True, "Troca solicitada com sucesso"

    @staticmethod
    @transaction.atomic
    def aprovar_troca(troca: TrocaServico) -> Tuple[bool, str]:
        """
        Aprova uma troca de serviço.
        Retorna (sucesso, mensagem)
        """
        if troca.status != 'PENDENTE':
            return False, "A troca precisa estar pendente para ser aprovada"

        # Obter as nomeações dos militares
        nomeacao_solicitante = Nomeacao.objects.get(
            escala_militar__militar=troca.militar_solicitante,
            data=troca.data_troca
        )

        nomeacao_trocado = Nomeacao.objects.get(
            escala_militar__militar=troca.militar_trocado,
            data=troca.data_troca
        )

        # Trocar as posições
        nomeacao_solicitante.e_reserva = True
        nomeacao_solicitante.save()

        nomeacao_trocado.e_reserva = False
        nomeacao_trocado.save()

        # Atualizar status da troca
        troca.status = 'APROVADA'
        troca.data_aprovacao = timezone.now()
        troca.save()

        return True, "Troca aprovada com sucesso"

    @staticmethod
    def rejeitar_troca(troca: TrocaServico) -> Tuple[bool, str]:
        """
        Rejeita uma troca de serviço.
        Retorna (sucesso, mensagem)
        """
        if troca.status != 'PENDENTE':
            return False, "A troca precisa estar pendente para ser rejeitada"

        troca.status = 'REJEITADA'
        troca.save()

        return True, "Troca rejeitada com sucesso"

    @staticmethod
    def agendar_destroca(troca: TrocaServico, data_destroca: date) -> Tuple[bool, str]:
        """
        Agenda a destroca para uma data específica.
        Retorna (sucesso, mensagem)
        """
        if troca.status != 'APROVADA':
            return False, "A troca precisa estar aprovada para agendar a destroca"

        # Verificar se o militar trocado está disponível na data da destroca
        disponivel, mensagem = EscalaService.verificar_disponibilidade_militar(
            troca.militar_trocado,
            data_destroca
        )

        if not disponivel:
            return False, f"O militar trocado não está disponível na data da destroca: {mensagem}"

        # Agendar a destroca
        troca.data_destroca = data_destroca
        troca.save()

        return True, "Destroca agendada com sucesso"

    @staticmethod
    @transaction.atomic
    def executar_destroca(troca: TrocaServico) -> Tuple[bool, str]:
        """
        Executa a destroca de uma troca de serviço.
        Retorna (sucesso, mensagem)
        """
        if not troca.data_destroca:
            return False, "Data da destroca não definida"

        # Obter as nomeações dos militares
        nomeacao_solicitante = Nomeacao.objects.get(
            escala_militar__militar=troca.militar_solicitante,
            data=troca.data_destroca
        )

        nomeacao_trocado = Nomeacao.objects.get(
            escala_militar__militar=troca.militar_trocado,
            data=troca.data_destroca
        )

        # Restaurar as posições originais
        nomeacao_solicitante.e_reserva = False
        nomeacao_solicitante.save()

        nomeacao_trocado.e_reserva = True
        nomeacao_trocado.save()

        # Atualizar status da troca
        troca.status = 'CONCLUIDA'
        troca.save()

        return True, "Destroca executada com sucesso"

    @staticmethod
    def obter_trocas_pendentes() -> List[TrocaServico]:
        """
        Retorna todas as trocas pendentes.
        """
        return TrocaServico.objects.filter(status='PENDENTE').select_related(
            'militar_solicitante',
            'militar_trocado'
        )

    @staticmethod
    def obter_trocas_por_militar(militar: Militar) -> List[TrocaServico]:
        """
        Retorna todas as trocas de um militar (solicitadas ou recebidas).
        """
        return TrocaServico.objects.filter(
            models.Q(militar_solicitante=militar) | models.Q(militar_trocado=militar)
        ).select_related(
            'militar_solicitante',
            'militar_trocado'
        ) 