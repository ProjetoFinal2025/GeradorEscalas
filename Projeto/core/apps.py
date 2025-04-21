from django.apps import AppConfig
import reversion

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from .models import Escala, Servico, Militar, Dispensa, EscalaMilitar, RegraNomeacao
        from . import signals
        from . import initial_setup

        #Escolhe que modelos tem backup

        if not reversion.is_registered(Militar):
            reversion.register(Militar)

        if not reversion.is_registered(Dispensa):
            reversion.register(Dispensa, follow=("militar",))

        if not reversion.is_registered(Servico):
            reversion.register(Servico, follow=("militares",))

        if not reversion.is_registered(Escala):
            reversion.register(Escala)

        if not reversion.is_registered(RegraNomeacao):
            reversion.register(RegraNomeacao, follow=("servico",))

