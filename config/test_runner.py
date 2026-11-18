"""Runner de testes que nunca escreve na pasta media/ real.

Durante `manage.py test`, MEDIA_ROOT aponta para UM diretório temporário criado só para esta
execução (popular_loja, uploads etc. gravam lá). No fim o override é desfeito e somente esse
diretório é apagado, depois de conferir que ele está dentro do temp do sistema e foi criado aqui.

Classes que usam o próprio @override_settings(MEDIA_ROOT=...) continuam valendo dentro delas.
Obs.: com --parallel os processos filhos não herdam este override; a suíte roda em série.
"""
import shutil
import tempfile
from pathlib import Path

from django.test.runner import DiscoverRunner
from django.test.utils import override_settings

PREFIXO = "nexar_test_media_suite_"


class MediaIsoladaRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        # Path (não str): popular_loja faz settings.MEDIA_ROOT / "produtos"
        self._media_temp = Path(tempfile.mkdtemp(prefix=PREFIXO)).resolve()
        self._media_override = override_settings(MEDIA_ROOT=self._media_temp)
        self._media_override.enable()

    def teardown_test_environment(self, **kwargs):
        override = getattr(self, "_media_override", None)
        if override is not None:
            override.disable()
            self._media_override = None
        pasta = getattr(self, "_media_temp", None)
        self._media_temp = None
        if pasta is not None:
            raiz_temp = Path(tempfile.gettempdir()).resolve()
            # só apaga o que este runner criou: dentro do temp do sistema e com o prefixo dele
            if pasta.parent == raiz_temp and pasta.name.startswith(PREFIXO) and pasta.is_dir():
                shutil.rmtree(pasta, ignore_errors=True)
        super().teardown_test_environment(**kwargs)
