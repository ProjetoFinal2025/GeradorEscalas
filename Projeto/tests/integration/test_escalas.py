from django.test import TestCase
from datetime import date, timedelta
from core.models import (
    Militar, Servico, Escala, EscalaMilitar, 
    Nomeacao, RegraNomeacao
)

class EscalaIntegrationTest(TestCase):
    def setUp(self):
        # Criar militares
        self.militar1 = Militar.objects.create(
            nim='12345678',
            nome='João Silva',
            posto='SOL',
            funcao='Condutor',
            telefone=912345678,
            email='joao@exemplo.com'
        )
        self.militar2 = Militar.objects.create(
            nim='87654321',
            nome='Maria Santos',
            posto='SOL',
            funcao='Condutor',
            telefone=987654321,
            email='maria@exemplo.com'
        )

        # Criar serviço
        self.servico = Servico.objects.create(
            nome='Serviço de Guarda',
            hora_inicio='08:00',
            hora_fim='17:00',
            n_elementos=1,
            n_reservas=1
        )

        # Criar regra de nomeação
        self.regra = RegraNomeacao.objects.create(
            servico=self.servico,
            tipo_folga='mesma_escala',
            horas_minimas=24,
            prioridade_modernos=True,
            considerar_ultimo_servico=True,
            permitir_trocas=True
        )

    def test_fluxo_completo_escala(self):
        # Criar escala
        escala = Escala.objects.create(
            servico=self.servico,
            e_escala_b=False,
            prevista=True
        )
        
        # Adicionar militares à escala
        escala_militar1 = EscalaMilitar.objects.create(
            escala=escala,
            militar=self.militar1,
            ordem=1
        )
        escala_militar2 = EscalaMilitar.objects.create(
            escala=escala,
            militar=self.militar2,
            ordem=2
        )
        
        # Criar nomeações
        data_hoje = date.today()
        nomeacao1 = Nomeacao.objects.create(
            escala_militar=escala_militar1,
            data=data_hoje,
            e_reserva=False
        )
        nomeacao2 = Nomeacao.objects.create(
            escala_militar=escala_militar2,
            data=data_hoje,
            e_reserva=True
        )
        
        # Verificar integridade
        self.assertEqual(escala.servico, self.servico)
        self.assertEqual(escala_militar1.militar, self.militar1)
        self.assertEqual(escala_militar2.militar, self.militar2)
        self.assertEqual(nomeacao1.escala_militar, escala_militar1)
        self.assertEqual(nomeacao2.escala_militar, escala_militar2)
        self.assertFalse(nomeacao1.e_reserva)
        self.assertTrue(nomeacao2.e_reserva)

    def test_verificar_folga_entre_servicos(self):
        # Criar primeira escala
        escala1 = Escala.objects.create(
            servico=self.servico,
            e_escala_b=False,
            prevista=True
        )
        escala_militar1 = EscalaMilitar.objects.create(
            escala=escala1,
            militar=self.militar1
        )
        
        # Criar nomeação para hoje
        data_hoje = date.today()
        Nomeacao.objects.create(
            escala_militar=escala_militar1,
            data=data_hoje
        )
        
        # Verificar folga para amanhã
        folga = self.militar1.calcular_folga(data_hoje + timedelta(days=1), self.servico)
        self.assertEqual(folga, 24)  # 24 horas de folga

    def test_verificar_disponibilidade_com_nomeacao(self):
        # Criar escala
        escala = Escala.objects.create(
            servico=self.servico,
            e_escala_b=False,
            prevista=True
        )
        escala_militar = EscalaMilitar.objects.create(
            escala=escala,
            militar=self.militar1
        )
        
        # Criar nomeação para hoje
        data_hoje = date.today()
        Nomeacao.objects.create(
            escala_militar=escala_militar,
            data=data_hoje
        )
        
        # Verificar disponibilidade
        self.assertFalse(self.militar1.esta_disponivel(data_hoje))
        self.assertFalse(self.militar1.esta_disponivel(data_hoje + timedelta(days=1))) 