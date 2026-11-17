"""Testes do preço gravado no pedido (preco_unitario), da migração 0002 e das constraints.

Rodar com: python manage.py test loja
"""
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from .mock_data import PRODUTOS
from .models import Categoria, Pedido, Produto


class PrecoUnitarioTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create(username="cliente.teste")
        cls.categoria = Categoria.objects.create(nome="Teste")
        cls.produto = Produto.objects.create(nome="Camiseta", preco=Decimal("100.00"), categoria=cls.categoria)

    def test_mudar_preco_do_produto_nao_muda_total_do_pedido(self):
        pedido = Pedido.objects.create(usuario=self.usuario, produto=self.produto, tamanho="M",
                                       quantidade=3, preco_unitario=self.produto.preco)
        self.assertEqual(pedido.total, Decimal("300.00"))

        self.produto.preco = Decimal("150.00")
        self.produto.save()

        pedido = Pedido.objects.get(pk=pedido.pk)
        self.assertEqual(pedido.preco_unitario, Decimal("100.00"))
        self.assertEqual(pedido.total, Decimal("300.00"))

    def test_constraint_rejeita_quantidade_zero(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Pedido.objects.create(usuario=self.usuario, produto=self.produto, tamanho="M",
                                  quantidade=0, preco_unitario=Decimal("100.00"))

    def test_constraint_rejeita_preco_negativo(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Produto.objects.create(nome="Errado", preco=Decimal("-1.00"), categoria=self.categoria)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Pedido.objects.create(usuario=self.usuario, produto=self.produto, tamanho="M",
                                  quantidade=1, preco_unitario=Decimal("-1.00"))


class PopularLojaTest(TestCase):
    def test_popular_loja_grava_preco_unitario_igual_ao_preco(self):
        call_command("popular_loja", verbosity=0, stdout=StringIO())
        self.assertEqual(Pedido.objects.count(), 5)
        for pedido in Pedido.objects.select_related("produto"):
            self.assertEqual(pedido.preco_unitario, pedido.produto.preco)
        ana = Pedido.objects.get(usuario__username="ana.souza")
        self.assertEqual(ana.total, Decimal("449.70"))  # 3 x 149,90

    def test_popular_loja_nao_duplica(self):
        call_command("popular_loja", verbosity=0, stdout=StringIO())
        call_command("popular_loja", verbosity=0, stdout=StringIO())
        self.assertEqual(Produto.objects.count(), len(PRODUTOS))
        self.assertEqual(Pedido.objects.count(), 5)


class MigracaoPrecoUnitarioTest(TransactionTestCase):
    """Volta o banco para a 0001, cria um pedido antigo (sem preco_unitario) e aplica a 0002."""

    antes = [("loja", "0001_initial")]
    depois = [("loja", "0002_pedido_preco_unitario")]

    def tearDown(self):
        # deixa o banco de teste no estado mais recente para os outros testes
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_migracao_preenche_preco_unitario_com_preco_do_produto(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.antes)
        apps_antigos = executor.loader.project_state(self.antes).apps

        User_ = apps_antigos.get_model("auth", "User")
        Categoria_ = apps_antigos.get_model("loja", "Categoria")
        Produto_ = apps_antigos.get_model("loja", "Produto")
        Pedido_ = apps_antigos.get_model("loja", "Pedido")
        usuario = User_.objects.create(username="antigo")
        categoria = Categoria_.objects.create(nome="Bonés")
        produto = Produto_.objects.create(nome="Boné", preco=Decimal("129.90"), categoria=categoria)
        pedido_id = Pedido_.objects.create(usuario=usuario, produto=produto, tamanho="M", quantidade=2).pk

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.depois)
        apps_novos = executor.loader.project_state(self.depois).apps

        pedido = apps_novos.get_model("loja", "Pedido").objects.get(pk=pedido_id)
        self.assertEqual(pedido.preco_unitario, Decimal("129.90"))


class PrecoAutomaticoTest(TestCase):
    """Pedido criado sem preco_unitario (ex.: pelo /admin/) copia o preço do produto."""

    def test_save_preenche_preco_unitario(self):

        cat = Categoria.objects.create(nome="Teste auto")
        prod = Produto.objects.create(nome="Peça", preco=Decimal("88.50"), estoque=5, categoria=cat)
        user = User.objects.create_user("auto_preco")
        pedido = Pedido.objects.create(usuario=user, produto=prod, tamanho="M", quantidade=2)
        self.assertEqual(pedido.preco_unitario, Decimal("88.50"))
        self.assertEqual(pedido.total, Decimal("177.00"))
        self.assertIsNone(Pedido(quantidade=2).total)
