from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction


class Command(BaseCommand):
    help = 'Redefine a palavra-passe de um utilizador'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list',
            action='store_true',
            help='Lista todos os utilizadores disponíveis',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Força a alteração mesmo se a palavra-passe for fraca',
        )
        parser.add_argument(
            'username',
            nargs='?',
            type=str,
            help='Nome do utilizador'
        )
        parser.add_argument(
            'new_password',
            nargs='?',
            type=str,
            help='Nova palavra-passe'
        )

    def handle(self, *args, **options):
        if options['list']:
            self.list_users()
            return

        username = options['username']
        new_password = options['new_password']
        force = options['force']

        if not username or not new_password:
            raise CommandError(
                'É necessário fornecer username e new_password. '
                'Use --list para ver os utilizadores disponíveis.'
            )

        # Validar a palavra-passe
        if not force and len(new_password) < 8:
            raise CommandError(
                'A palavra-passe deve ter pelo menos 8 caracteres. '
                'Use --force para ignorar esta validação.'
            )

        try:
            with transaction.atomic():
                user = User.objects.get(username=username)
                user.set_password(new_password)
                user.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Palavra-passe do utilizador "{username}" foi redefinida com sucesso!'
                    )
                )
                self.stdout.write(
                    f'🔐 Nova palavra-passe: {new_password}'
                )

        except User.DoesNotExist:
            raise CommandError(f'❌ Utilizador "{username}" não encontrado!')
        except Exception as e:
            raise CommandError(f'❌ Erro ao redefinir palavra-passe: {e}')

    def list_users(self):
        """Lista todos os utilizadores disponíveis"""
        users = User.objects.all()
        
        if not users.exists():
            self.stdout.write('Nenhum utilizador encontrado.')
            return

        self.stdout.write('\n📋 Utilizadores disponíveis:')
        self.stdout.write('-' * 50)
        
        for user in users:
            email = user.email if user.email else '(sem email)'
            is_active = '✅' if user.is_active else '❌'
            self.stdout.write(f'{is_active} {user.username} ({email})')
        
        self.stdout.write('-' * 50) 