from django.core.management.base import BaseCommand
from core.models import Militar
import random
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password

class Command(BaseCommand):
    help = 'Popula a base de dados com 40 militares de diferentes postos'

    def handle(self, *args, **kwargs):
        # Lista de nomes fictícios
        nomes = [
            'João Silva', 'Maria Santos', 'Pedro Oliveira', 'Ana Costa', 'Carlos Ferreira',
            'Sofia Rodrigues', 'Miguel Martins', 'Inês Pereira', 'Tiago Sousa', 'Beatriz Lima',
            'Rui Carvalho', 'Catarina Almeida', 'André Gomes', 'Mariana Ribeiro', 'Diogo Fernandes',
            'Laura Pinto', 'Ricardo Marques', 'Carolina Gonçalves', 'Bruno Lopes', 'Matilde Castro',
            'Francisco Teixeira', 'Clara Correia', 'Gonçalo Mendes', 'Diana Moreira', 'Hugo Azevedo',
            'Eva Barbosa', 'Daniel Tavares', 'Leonor Pinto', 'Tomás Coelho', 'Bianca Cardoso',
            'Vasco Machado', 'Mafalda Barros', 'Rafael Baptista', 'Sara Campos', 'Guilherme Fonseca',
            'Teresa Morais', 'Duarte Nunes', 'Margarida Leal', 'Filipe Matos', 'Isabel Guerreiro'
        ]

        # Lista de funções fictícias
        funcoes = [
            'Operador de Sistemas', 'Técnico de Informática', 'Administrador de Redes',
            'Especialista em Cibersegurança', 'Gestor de Projetos', 'Analista de Sistemas',
            'Programador', 'Técnico de Suporte', 'Gestor de Base de Dados', 'Consultor IT'
        ]

        # Postos disponíveis
        postos = [
            'COR', 'TCOR', 'MAJ', 'CAP', 'TEN', 'ALF', 'ASP', 'SCH', 'SAJ', '1SARG',
            '2SARG', 'FUR', '2FUR', 'CABSEC', 'CADJ', '1CAB', '2CAB', 'SOL'
        ]

        # Password padrão para todos os militares
        password_padrao = 'Exercito2024!'

        # Criar 40 militares
        for i in range(40):
            nim = 10000000 + i
            nome = random.choice(nomes)
            posto = random.choice(postos)
            funcao = random.choice(funcoes)
            telefone = 900000000 + i
            email = f"{nome.lower().replace(' ', '.')}@exemplo.pt"
            
            # Criar o utilizador
            username = str(nim)
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password_padrao,
                first_name=nome.split()[0],
                last_name=' '.join(nome.split()[1:])
            )
            
            # Criar o militar
            militar = Militar.objects.create(
                nim=nim,
                user=user,
                nome=nome,
                posto=posto,
                funcao=funcao,
                e_administrador=False,
                telefone=telefone,
                email=email,
                ordem_semana=random.randint(1, 10),
                ordem_fds=random.randint(1, 10)
            )
            
            self.stdout.write(self.style.SUCCESS(f'Criado militar: {militar}'))

        self.stdout.write(self.style.SUCCESS('Foram criados 40 militares com sucesso!'))
        self.stdout.write(self.style.SUCCESS(f'Password padrão para todos os militares: {password_padrao}')) 