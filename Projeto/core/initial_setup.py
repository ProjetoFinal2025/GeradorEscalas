from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

@receiver(post_migrate)
def criar_role_administrador(sender, **kwargs):
    from .models import Role, Escala, Servico, Militar, Dispensa

    role, created = Role.objects.get_or_create(
        nome="Administrador",
        defaults={"descricao": "Papel padrão para administradores militares"}
    )

    if created:
        modelos = [Escala, Servico, Militar, Dispensa]
        for modelo in modelos:
            ct = ContentType.objects.get_for_model(modelo)
            permissoes = Permission.objects.filter(
                content_type=ct,
                codename__in=[
                    f"view_{modelo.__name__.lower()}",
                    f"change_{modelo.__name__.lower()}"
                ]
            )
            role.permissions.add(*permissoes)
