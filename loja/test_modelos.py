"""Testes do preço gravado no pedido (preco_unitario), da migração 0004 e das constraints.

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
    """Volta o banco para a 0003, cria um pedido antigo (sem preco_unitario) e aplica a 0004."""

    antes = [("loja", "0003_cores_e_modelos_locais")]
    depois = [("loja", "0004_pedido_preco_unitario")]

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


class MigracaoBloqueiaDadosInvalidosTest(TransactionTestCase):
    """A 0004 não corrige dados: com quantidade 0 ou preço negativo ela aborta e desfaz tudo."""

    antes = [("loja", "0003_cores_e_modelos_locais")]
    depois = [("loja", "0004_pedido_preco_unitario")]

    def tearDown(self):
        # remove os dados inválidos (senão a própria 0004 barra a volta ao estado final)
        with connection.cursor() as cursor:
            for tabela in ("pedidos", "produtos", "categorias", "auth_user"):
                cursor.execute(f"DELETE FROM {connection.ops.quote_name(tabela)}")
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def _preparar_0003(self, quantidade=1, preco=Decimal("50.00")):
        executor = MigrationExecutor(connection)
        executor.migrate(self.antes)
        apps_antigos = executor.loader.project_state(self.antes).apps
        usuario = apps_antigos.get_model("auth", "User").objects.create(username="legado")
        categoria = apps_antigos.get_model("loja", "Categoria").objects.create(nome="Legado")
        produto = apps_antigos.get_model("loja", "Produto").objects.create(
            nome="Antigo", preco=preco, categoria=categoria)
        pedido = apps_antigos.get_model("loja", "Pedido").objects.create(
            usuario=usuario, produto=produto, tamanho="M", quantidade=quantidade)
        return produto.pk, pedido.pk

    def _migrar_espera_erro(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        with self.assertRaises(RuntimeError) as ctx:
            executor.migrate(self.depois)
        return str(ctx.exception)

    def _colunas_pedidos(self):
        with connection.cursor() as cursor:
            return [c.name for c in connection.introspection.get_table_description(cursor, "pedidos")]

    def _assert_continua_na_0003(self):
        executor = MigrationExecutor(connection)
        self.assertNotIn(self.depois[0], executor.loader.applied_migrations)
        self.assertIn(self.antes[0], executor.loader.applied_migrations)
        self.assertNotIn("preco_unitario", self._colunas_pedidos())

    def test_quantidade_zero_bloqueia_migracao(self):
        _, pedido_id = self._preparar_0003(quantidade=0)
        mensagem = self._migrar_espera_erro()
        self.assertIn("1 pedido(s) com quantidade menor que 1", mensagem)
        self.assertIn(f"ids: {pedido_id}", mensagem)
        self.assertIn("Corrija", mensagem)
        self._assert_continua_na_0003()
        with connection.cursor() as cursor:
            cursor.execute("SELECT quantidade FROM pedidos WHERE id = %s", [pedido_id])
            self.assertEqual(cursor.fetchone()[0], 0)  # nada foi corrigido sozinho

    def test_preco_negativo_bloqueia_migracao(self):
        produto_id, _ = self._preparar_0003(preco=Decimal("-10.00"))
        mensagem = self._migrar_espera_erro()
        self.assertIn("1 produto(s) com preço negativo", mensagem)
        self.assertIn(f"ids: {produto_id}", mensagem)
        self._assert_continua_na_0003()
        with connection.cursor() as cursor:
            cursor.execute("SELECT preco FROM produtos WHERE id = %s", [produto_id])
            self.assertEqual(Decimal(str(cursor.fetchone()[0])), Decimal("-10.00"))


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
