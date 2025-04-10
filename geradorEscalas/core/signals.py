from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from .models import Militar, Servico, Dispensa, Escala, Configuracao, Log
from django.contrib.auth.models import User

# Debug
# print("signals.py LOADED")

def criar_log(nim_admin, acao, modelo, tipo_acao):
    """Função auxiliar para criar logs"""
    Log.objects.create(
        nim_admin=nim_admin,
        acao=acao,
        modelo=modelo,
        tipo_acao=tipo_acao
    )

@receiver([post_save, post_delete], sender=Militar)
def log_alteracoes_militar(sender, instance, **kwargs):
    """Regista alterações em Militar"""
    if 'created' in kwargs:
        if kwargs['created']:
            acao = f"Criado militar: {instance.posto} {instance.nome}"
            tipo_acao = 'CREATE'
        else:
            acao = f"Atualizado militar: {instance.posto} {instance.nome}"
            tipo_acao = 'UPDATE'
    else:
        acao = f"Removido militar: {instance.posto} {instance.nome}"
        tipo_acao = 'DELETE'
    
    # TODO: Obter o NIM do administrador atual
    # Por enquanto, usando um valor temporário
    criar_log(12345678, acao, 'Militar', tipo_acao)

@receiver([post_save, post_delete], sender=Servico)
def log_alteracoes_servico(sender, instance, **kwargs):
    """Regista alterações em Serviço"""
    if 'created' in kwargs:
        if kwargs['created']:
            acao = f"Criado serviço: {instance.nome}"
            tipo_acao = 'CREATE'
        else:
            acao = f"Atualizado serviço: {instance.nome}"
            tipo_acao = 'UPDATE'
    else:
        acao = f"Removido serviço: {instance.nome}"
        tipo_acao = 'DELETE'
    
    criar_log(12345678, acao, 'Servico', tipo_acao)

@receiver([post_save, post_delete], sender=Dispensa)
def log_alteracoes_dispensa(sender, instance, **kwargs):
    """Regista alterações em Dispensa"""
    if 'created' in kwargs:
        if kwargs['created']:
            acao = f"Criada dispensa para {instance.militar.nome} ({instance.data_inicio} - {instance.data_fim})"
            tipo_acao = 'CREATE'
        else:
            acao = f"Atualizada dispensa para {instance.militar.nome}"
            tipo_acao = 'UPDATE'
    else:
        acao = f"Removida dispensa de {instance.militar.nome}"
        tipo_acao = 'DELETE'
    
    criar_log(12345678, acao, 'Dispensa', tipo_acao)

@receiver([post_save, post_delete], sender=Escala)
def log_alteracoes_escala(sender, instance, **kwargs):
    """Regista alterações em Escala"""
    if 'created' in kwargs:
        if kwargs['created']:
            # CRIA ERRO POIS VARIAVEL NAO EXISTE
            #acao = f"Criada escala: {instance.militar.nome} para {instance.data}"
            acao = ''
            tipo_acao = 'CREATE'
        else:
            acao = f"Atualizada escala: {instance.militar.nome} para {instance.data}"
            tipo_acao = 'UPDATE'
    else:
       # CRIA ERRO POIS VARIAVEL NAO EXISTE
       # acao = f"Removida escala de {instance.militar.nome} para {instance.data}"
        acao = ''
        tipo_acao = 'DELETE'
    
    criar_log(12345678, acao, 'Escala', tipo_acao)

@receiver([post_save, post_delete], sender=Configuracao)
def log_alteracoes_configuracao(sender, instance, **kwargs):
    """Regista alterações em Configuração"""
    if 'created' in kwargs:
        if kwargs['created']:
            acao = "Criada nova configuração"
            tipo_acao = 'CREATE'
        else:
            acao = "Atualizada configuração"
            tipo_acao = 'UPDATE'
    else:
        acao = "Removida configuração"
        tipo_acao = 'DELETE'
    
    criar_log(12345678, acao, 'Configuracao', tipo_acao)

@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    """Regista logins no sistema"""
    # Assumindo que o user tem um campo nim
    criar_log(
        user.nim if hasattr(user, 'nim') else 12345678,
        f"Login no sistema: {user.username}",
        'User',
        'LOGIN'
    )

@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    """Regista logouts no sistema"""
    if user:  # user pode ser None se a sessão expirou
        criar_log(
            user.nim if hasattr(user, 'nim') else 12345678,
            f"Logout do sistema: {user.username}",
            'User',
            'LOGOUT'
        ) 



#################### User's #################################

# Cria o Respetivo utilizador quando militar é apagado
@receiver(post_save, sender=Militar)
def criar_user_para_militar(sender, instance, created, **kwargs):
    if created and not instance.user:
        username = str(instance.nim)
        password = "mel"

        # Evita duplicação
        if not User.objects.filter(username=username).exists():
            user = User.objects.create_user(
                username=username,
                password=password,
                email=instance.email
            )

            instance.user = user
            instance.save()

# Apaga o Respetivo utilizador quando militar é apagado
@receiver(post_delete, sender=Militar)
def apagar_user_com_militar(sender, instance, **kwargs):
    if instance.user:
        print(f"User{instance.user.username} ligado ao Militar {instance.nim} será eliminado")
        instance.user.delete()
