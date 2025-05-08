from decouple import config
from django.core.management.base import BaseCommand
from ...models import Militar
import random
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.db.models.signals import post_save
from core.signals import criar_user_para_militar

class Command(BaseCommand):
    help = 'Popula a base de dados com 45 militares de diferentes postos'

    def handle(self, *args, **kwargs):
        # Desativar temporariamente o sinal de criação de utilizador
        post_save.disconnect(criar_user_para_militar, sender=Militar)

        # Lista de postos e quantidades
        postos = {
            'CAP': 5,    # Capitão
            'TEN': 5,    # Tenente
            'ALF': 5,    # Alferes
            '1SARG': 5,  # Primeiro-Sargento
            '2SARG': 5,  # Segundo-Sargento
            'FUR': 5,    # Furriel
            '2FUR': 5,   # 2ºFurriel
            'CABSEC': 5, # Cabo de Secção
            '1CAB': 5,   # Primeiro-Cabo
            'SOL': 5     # Soldado
        }

        # Lista de nomes para gerar nomes aleatórios
        nomes = [
            'Silva', 'Santos', 'Oliveira', 'Sousa', 'Rodrigues', 'Ferreira', 'Pereira', 'Costa',
            'Martins', 'Jesus', 'Lopes', 'Marques', 'Gomes', 'Ribeiro', 'Carvalho', 'Fernandes',
            'Almeida', 'Antunes', 'Correia', 'Mendes', 'Nunes', 'Soares', 'Vieira', 'Moreira',
            'Gonçalves', 'Dias', 'Teixeira', 'Araújo', 'Monteiro', 'Ramos'
        ]

        # Lista de funções
        funcoes = [
            'Comandante de Companhia', 'Comandante de Pelotão', 'Comandante de Secção',
            'Chefe de Secção', 'Operador de Sistemas', 'Condutor', 'Operador de Rádio',
            'Atirador', 'Observador', 'Mecânico', 'Condutor de Viatura', 'Operador de Arma'
        ]

        # Gerar militares
        for posto, quantidade in postos.items():
            for i in range(quantidade):
                # Gerar NIM único (8 dígitos)
                nim = random.randint(10000000, 99999999)
                while Militar.objects.filter(nim=nim).exists():
                    nim = random.randint(10000000, 99999999)

                # Gerar nome
                nome = f"{random.choice(nomes)} {random.choice(nomes)}"

                # Gerar telefone (9 dígitos)
                telefone = random.randint(900000000, 999999999)

                # Gerar email
                email = f"{nome.lower().replace(' ', '.')}@exército.pt"

                # Criar militar
                militar = Militar.objects.create(
                    nim=nim,
                    nome=nome,
                    posto=posto,
                    funcao=random.choice(funcoes),
                    telefone=telefone,
                    email=email
                )

                self.stdout.write(
                    self.style.SUCCESS(f'Criado militar: {militar}')
                )

        # Reativar o sinal de criação de utilizador
        post_save.connect(criar_user_para_militar, sender=Militar)

        self.stdout.write(
            self.style.SUCCESS('Base de dados populada com sucesso!')
        )