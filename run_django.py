import os
import sys
import django
from django.core.management import execute_from_command_line

with open("log_arranque.txt", "w") as f:
    f.write("A iniciar o Django...\n")
    # Garantir que o diretório de trabalho é o do executável
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    f.write("Diretório de trabalho: " + os.getcwd() + "\n")

print('A iniciar o Django...')
print('Diretório de trabalho:', os.getcwd())

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Projeto.geradorEscalas.settings')
    print('DJANGO_SETTINGS_MODULE:', os.environ.get('DJANGO_SETTINGS_MODULE'))
    try:
        django.setup()
        print('Django setup concluído.')
        # Iniciar o servidor Django
        execute_from_command_line(['manage.py', 'runserver', '0.0.0.0:8000'])
    except Exception as e:
        print('Erro ao iniciar o Django:', e)
        with open("log_arranque.txt", "a") as f:
            f.write("Erro ao iniciar o Django: " + str(e) + "\n")
        input('Prima Enter para sair...') 