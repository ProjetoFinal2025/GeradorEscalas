#!/usr/bin/env python
"""
Script para redefinir a palavra-passe de um utilizador no Django.
Uso: python reset_password.py nome_utilizador nova_palavra_passe
"""

import os
import sys
import django

# Configurar o ambiente Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geradorEscalas.settings')
django.setup()

from django.contrib.auth.models import User
from django.core.management import execute_from_command_line

def reset_password(username, new_password):
    """
    Redefine a palavra-passe de um utilizador
    """
    try:
        # Procurar o utilizador
        user = User.objects.get(username=username)
        
        # Definir a nova palavra-passe
        user.set_password(new_password)
        user.save()
        
        print(f"✅ Palavra-passe do utilizador '{username}' foi redefinida com sucesso!")
        return True
        
    except User.DoesNotExist:
        print(f"❌ Erro: Utilizador '{username}' não encontrado!")
        return False
    except Exception as e:
        print(f"❌ Erro ao redefinir palavra-passe: {e}")
        return False

def list_users():
    """
    Lista todos os utilizadores disponíveis
    """
    users = User.objects.all()
    print("\n📋 Utilizadores disponíveis:")
    print("-" * 40)
    for user in users:
        print(f"  • {user.username} ({user.email})")
    print("-" * 40)

def main():
    if len(sys.argv) == 1:
        print("🔧 Script para Redefinir Palavra-passe de Utilizador")
        print("=" * 50)
        print("\nUso:")
        print("  python reset_password.py nome_utilizador nova_palavra_passe")
        print("  python reset_password.py --list (para listar utilizadores)")
        print("\nExemplo:")
        print("  python reset_password.py admin nova_palavra_passe123")
        print()
        list_users()
        return
    
    if len(sys.argv) == 2 and sys.argv[1] == '--list':
        list_users()
        return
    
    if len(sys.argv) != 3:
        print("❌ Erro: Número incorreto de argumentos!")
        print("Uso: python reset_password.py nome_utilizador nova_palavra_passe")
        return
    
    username = sys.argv[1]
    new_password = sys.argv[2]
    
    # Validar a palavra-passe
    if len(new_password) < 8:
        print("⚠️  Aviso: A palavra-passe deve ter pelo menos 8 caracteres!")
        response = input("Deseja continuar mesmo assim? (s/N): ")
        if response.lower() != 's':
            return
    
    # Redefinir a palavra-passe
    success = reset_password(username, new_password)
    
    if success:
        print(f"\n🔐 A palavra-passe do utilizador '{username}' foi alterada para: {new_password}")
        print("💡 Lembre-se de partilhar a nova palavra-passe de forma segura!")

if __name__ == '__main__':
    main() 