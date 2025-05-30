from django.test import TestCase
from django.core.exceptions import ValidationError
from core.models import RegraNomeacao, Servico
from django.db.utils import IntegrityError

class RegraNomeacaoTest(TestCase):
    def setUp(self):
        self.servico = Servico.objects.create(
            nome='Serviço de Guarda',
            hora_inicio='08:00',
            hora_fim='17:00'
        )

    def test_criar_regra_valida(self):
        regra = RegraNomeacao.objects.create(
            servico=self.servico,
            tipo_folga='mesma_escala',
            horas_minimas=24,
            prioridade_modernos=True,
            considerar_ultimo_servico=True,
            permitir_trocas=True
        )
        
        self.assertEqual(regra.servico, self.servico)
        self.assertEqual(regra.tipo_folga, 'mesma_escala')
        self.assertEqual(regra.horas_minimas, 24)
        self.assertTrue(regra.prioridade_modernos)
        self.assertTrue(regra.considerar_ultimo_servico)
        self.assertTrue(regra.permitir_trocas)

    def test_regra_duplicada(self):
        # Criar primeira regra
        RegraNomeacao.objects.create(
            servico=self.servico,
            tipo_folga='mesma_escala',
            horas_minimas=24
        )
        
        # Tentar criar regra duplicada
        with self.assertRaises((ValidationError, IntegrityError)):
            RegraNomeacao.objects.create(
                servico=self.servico,
                tipo_folga='mesma_escala',
                horas_minimas=48
            )

    def test_regras_diferentes_tipos(self):
        # Criar regra para mesma escala
        regra_mesma = RegraNomeacao.objects.create(
            servico=self.servico,
            tipo_folga='mesma_escala',
            horas_minimas=24
        )
        
        # Criar regra para entre escalas
        regra_entre = RegraNomeacao.objects.create(
            servico=self.servico,
            tipo_folga='entre_escalas',
            horas_minimas=48
        )
        
        self.assertEqual(regra_mesma.tipo_folga, 'mesma_escala')
        self.assertEqual(regra_entre.tipo_folga, 'entre_escalas')
        self.assertEqual(regra_mesma.horas_minimas, 24)
        self.assertEqual(regra_entre.horas_minimas, 48) 