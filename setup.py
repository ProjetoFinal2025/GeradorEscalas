from cx_Freeze import setup, Executable
import os

# Incluir ficheiros de templates e static
includefiles = [
    ('Projeto', 'Projeto'),
    ('Projeto/core/templates', 'Projeto/core/templates'),
    ('Projeto/core/static', 'Projeto/core/static'),
]

build_exe_options = {
    'packages': ['os', 'django', 'Projeto', 'Projeto.core'],
    'include_files': includefiles,
    'excludes': [],
}

setup(
    name='GeradorEscalas',
    version='1.0',
    description='Projeto Django empacotado com cx_Freeze',
    options={'build_exe': build_exe_options},
    executables=[Executable('run_django.py', base=None)],
) 