from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_save


class LojaConfig(AppConfig):
    name = 'loja'

    def ready(self):
        from .grupos import acertar_grupo
        post_save.connect(acertar_grupo, sender=settings.AUTH_USER_MODEL, dispatch_uid="loja_acertar_grupo")
