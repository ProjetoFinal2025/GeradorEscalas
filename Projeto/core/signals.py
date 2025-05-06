from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .models import Militar, Servico, Dispensa, Escala, Log, Role, EscalaMilitar, Nomeacao
from decouple import config

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
    # ► extrair intervalo de datas ligado a esta Escala
    datas = list(Nomeacao.objects.filter(escala_militar__escala=instance).values_list('data', flat=True))
    if datas:
        if len(set(datas)) == 1:
            data_str = datas[0].strftime('%d/%m/%Y')
        else:
            data_str = f"{min(datas).strftime('%d/%m/%Y')} – {max(datas).strftime('%d/%m/%Y')}"
    else:
        data_str = 'sem data'

    # ► compor mensagem
    if kwargs.get('created') is True:
        acao = f"Criada escala para o serviço {instance.servico.nome} ({data_str})"
        tipo_acao = 'CREATE'
    elif 'created' in kwargs:
        acao = f"Atualizada escala para o serviço {instance.servico.nome} ({data_str})"
        tipo_acao = 'UPDATE'
    else:
        acao = f"Removida escala do serviço {instance.servico.nome} ({data_str})"
        tipo_acao = 'DELETE'

    criar_log(12345678, acao, 'Escala', tipo_acao)

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
        password = config('USER_PASSWORD')

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

# Torna o Muilitar em administrador consoante a respetiva bool
@receiver(post_save, sender=Militar)
def atualizar_user_com_base_em_administrador(sender, instance, **kwargs):
    user = instance.user
    if not user:
        return

    try:
        # Pegamos o Role 'Administrador'
        role_admin = Role.objects.get(nome__iexact='Administrador')
    except Role.DoesNotExist:
        role_admin = None

    if instance.e_administrador and role_admin:
        # Caso o militar seja admin e exista esse Role
        user.is_staff = True
        user.is_superuser = False
        # Aplica as permissões definidas no Role
        user.user_permissions.set(role_admin.permissions.all())
    else:
        # Não é administrador
        user.is_staff = False
        user.is_superuser = False
        user.user_permissions.clear()

    user.save()

# Syncs the militares in a Escala When Serviço is updated
@receiver(m2m_changed, sender=Servico.militares.through)
def sync_escalas_when_servico_changes(sender, instance, action, **kwargs):
    if action not in ['post_add', 'post_remove', 'post_clear']:
        return

    servico = instance
    militares = list(servico.militares.all().order_by("nim"))

    for escala in servico.escalas.all():
        existing = EscalaMilitar.objects.filter(escala=escala).select_related("militar")
        existing_by_mil = {em.militar_id: em for em in existing}

        # Delete those not in the list anymore
        for em in existing:
            if em.militar not in militares:
                em.delete()

        # Add or re-order
        for idx, mil in enumerate(militares, start=1):
            em, created = EscalaMilitar.objects.get_or_create(
                escala=escala,
                militar=mil,
                defaults={"ordem": idx}
            )
            if not created:
                em.ordem= idx
                em.save()