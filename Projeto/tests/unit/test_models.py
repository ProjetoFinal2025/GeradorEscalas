from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from core.models import Militar, Dispensa, Servico, Escala, EscalaMilitar, Nomeacao

class MilitarModelTest(TestCase):
    def setUp(self):
        self.militar_data = {
            'nim': '12345678',
            'nome': 'João Silva',
            'posto': 'SOL',
            'funcao': 'Condutor',
            'telefone': 912345678,
            'email': 'joao@exemplo.com'
        }

    def test_criar_militar_valido(self):
        militar = Militar.objects.create(**self.militar_data)
        self.assertEqual(militar.nim, '12345678')
        self.assertEqual(militar.nome, 'João Silva')
        self.assertEqual(militar.posto, 'SOL')
        self.assertEqual(militar.funcao, 'Condutor')
        self.assertEqual(militar.telefone, 912345678)
        self.assertEqual(militar.email, 'joao@exemplo.com')

    def test_validacao_nim_invalido(self):
        self.militar_data['nim'] = 'ABC12345'
        militar = Militar(**self.militar_data)
        with self.assertRaises(ValidationError):
            militar.full_clean()

    def test_validacao_telefone_invalido(self):
        self.militar_data['telefone'] = 12345678
        militar = Militar(**self.militar_data)
        with self.assertRaises(ValidationError):
            militar.full_clean()

class MilitarDisponibilidadeTest(TestCase):
    def setUp(self):
        self.militar = Militar.objects.create(
            nim='12345678',
            nome='João Silva',
            posto='SOL',
            funcao='Condutor',
            telefone=912345678,
            email='joao@exemplo.com'
        )

    def test_disponibilidade_sem_dispensa(self):
        self.assertTrue(self.militar.esta_disponivel(date.today()))

    def test_disponibilidade_com_dispensa(self):
        Dispensa.objects.create(
            militar=self.militar,
            data_inicio=date.today(),
            data_fim=date.today() + timedelta(days=2),
            motivo='Férias'
        )
        self.assertFalse(self.militar.esta_disponivel(date.today()))
        self.assertFalse(self.militar.esta_disponivel(date.today() + timedelta(days=3)))

class MilitarFolgaTest(TestCase):
    def setUp(self):
        self.militar = Militar.objects.create(
            nim='12345678',
            nome='João Silva',
            posto='SOL',
            funcao='Condutor',
            telefone=912345678,
            email='joao@exemplo.com'
        )
        self.servico = Servico.objects.create(
            nome='Serviço de Guarda',
            hora_inicio='08:00',
            hora_fim='17:00'
        )

    def test_calculo_folga(self):
        escala = Escala.objects.create(servico=self.servico)
        escala_militar = EscalaMilitar.objects.create(
            escala=escala,
            militar=self.militar
        )
        
        ultimo_servico = date.today() - timedelta(days=2)
        Nomeacao.objects.create(
            escala_militar=escala_militar,
            data=ultimo_servico
        )
        
        folga = self.militar.calcular_folga(date.today(), self.servico)
        self.assertEqual(folga, 48)  # 48 horas de folga 