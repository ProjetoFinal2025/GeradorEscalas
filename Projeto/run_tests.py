#!/usr/bin/env python
"""
Script para executar os testes do projeto com opções úteis
"""
import os
import sys
import argparse
import subprocess

def main():
    parser = argparse.ArgumentParser(description='Executa os testes do projeto Gerador de Escalas')
    parser.add_argument('--type', choices=['all', 'unit', 'integration', 'interface', 'performance'], 
                        default='all', help='Tipo de testes a executar')
    parser.add_argument('--skip-interface', action='store_true', 
                        help='Pular testes de interface (útil em servidores CI/CD)')
    parser.add_argument('--verbose', '-v', action='store_true', 
                        help='Mostrar saída detalhada dos testes')
    
    args = parser.parse_args()
    
    # Configurar variáveis de ambiente
    env = os.environ.copy()
    if args.skip_interface:
        env['SKIP_INTERFACE_TESTS'] = 'true'
    
    # Construir o comando
    cmd = ['python', 'manage.py', 'test']
    
    # Adicionar padrão de teste com base no tipo
    if args.type == 'unit':
        cmd.append('tests.unit')
    elif args.type == 'integration':
        cmd.append('tests.integration')
    elif args.type == 'interface':
        cmd.append('tests.interface')
    elif args.type == 'performance':
        cmd.append('tests.performance')
    
    # Adicionar verbosidade se necessário
    if args.verbose:
        cmd.append('-v')
    
    # Executar o comando
    print(f"Executando: {' '.join(cmd)}")
    subprocess.run(cmd, env=env)

if __name__ == '__main__':
    main()
