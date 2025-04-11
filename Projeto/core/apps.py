from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # from .initial_setup import criar_role_administrador
        # criar_role_administrador()
        from . import signals
        from . import initial_setup