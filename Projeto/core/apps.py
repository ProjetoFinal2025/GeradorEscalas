from django.apps import AppConfig
import reversion

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from .models import User, Escala, Servico, Militar, Dispensa, EscalaMilitar, RegraNomeacao
        from . import signals
        from . import initial_setup

        #Escolhe que modelos tem backup
        if not reversion.is_registered(User):
            reversion.register(User)

        if not reversion.is_registered(Militar):
            reversion.register(Militar, follow=("user"))

        if not reversion.is_registered(Dispensa):
            reversion.register(Dispensa, follow=("militar",))

        if not reversion.is_registered(Servico):
            reversion.register(Servico, follow=("militares",))

        if not reversion.is_registered(Escala):
            reversion.register(Escala, follow=("militares_info",))

        if not reversion.is_registered(EscalaMilitar):
            reversion.register(EscalaMilitar, follow=("militar",))

        if not reversion.is_registered(RegraNomeacao):
            reversion.register(RegraNomeacao, follow=("servico",))

