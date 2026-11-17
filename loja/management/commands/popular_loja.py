"""python manage.py popular_loja: cadastra categorias, produtos, clientes e pedidos de exemplo."""
import shutil
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from loja.mock_data import CATEGORIAS, CORES, PEDIDOS, PRODUTOS
from loja.models import Categoria, Pedido, Produto


class Command(BaseCommand):
    help = "Cadastra categorias, produtos, clientes e pedidos de exemplo."

    @transaction.atomic
    def handle(self, *args, **opcoes):
        if Produto.objects.exists():
            self.stdout.write(self.style.WARNING("O banco já tem produtos. Nada foi alterado."))
            return

        # copia as fotos para media/produtos
        origem = settings.BASE_DIR / "static" / "img" / "produtos"
        destino = settings.MEDIA_ROOT / "produtos"
        destino.mkdir(parents=True, exist_ok=True)

        categorias = {c["id"]: Categoria.objects.create(nome=c["nome"]) for c in CATEGORIAS}

        produtos = {}
        for p in PRODUTOS:
            fotos = {}
            for campo in ("imagem", "imagem_2"):
                if p[campo]:
                    arquivo = p[campo].url.rsplit("/", 1)[1]
                    shutil.copy(origem / arquivo, destino / arquivo)
                    fotos[campo] = f"produtos/{arquivo}"
            produtos[p["nome"]] = Produto.objects.create(
                nome=p["nome"], descricao=p["descricao"], preco=Decimal(str(p["preco"])),
                estoque=p["estoque"], categoria=categorias[p["categoria_id"]],
                modelo_3d=p["modelo_3d"] or "", cor=CORES.get(p["nome"], ""), **fotos,
            )

        for ped in PEDIDOS:
            # clientes de exemplo (sem senha)
            cliente, _ = User.objects.get_or_create(username=ped["cliente"])
            pedido = Pedido.objects.create(usuario=cliente, produto=produtos[ped["produto"]],
                                           tamanho=ped["tamanho"], quantidade=ped["quantidade"])
            # volta a data do exemplo
            Pedido.objects.filter(pk=pedido.pk).update(data=timezone.make_aware(ped["data"]))

        self.stdout.write(self.style.SUCCESS(
            f"Pronto: {Categoria.objects.count()} categorias, {Produto.objects.count()} produtos, "
            f"{User.objects.count()} usuários e {Pedido.objects.count()} pedidos."))
