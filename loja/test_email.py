"""Política de e-mail único (case-insensitive), concorrência no cadastro, admin e migration 0005.

Rodar com: python manage.py test loja
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .forms import CadastroForm
from .models import Categoria, Pedido, Produto

SENHA = "Nexar-Senha-Forte-26"
ERRO = "Já existe uma conta com este e-mail."


def dados(**extra):
    d = {"username": "novo", "email": "novo@exemplo.com", "password1": SENHA, "password2": SENHA}
    d.update(extra)
    return d


class CadastroEmailTest(TestCase):
    url = reverse("loja:cadastro")

    def test_email_repetido_em_outra_caixa(self):
        User.objects.create_user("ana", "ana@x.com", SENHA)
        r = self.client.post(self.url, dados(username="ana2", email="Ana@X.com"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, ERRO)
        self.assertEqual(User.objects.count(), 1)

    def test_email_normalizado(self):
        self.client.post(self.url, dados(email="  Novo@Exemplo.COM "))
        self.assertEqual(User.objects.get(username="novo").email, "novo@exemplo.com")

    def test_erro_preserva_username_email_e_nao_devolve_senha(self):
        User.objects.create_user("ana", "ana@x.com", SENHA)
        r = self.client.post(self.url, dados(username="fulano", email="ANA@x.com"))
        html = r.content.decode()
        self.assertIn('value="fulano"', html)
        self.assertIn('value="ANA@x.com"', html)  # devolve o que a pessoa digitou
        self.assertNotIn(SENHA, html)

    def test_corrida_email_devolve_200_com_erro(self):
        # Outra requisição gravou o mesmo e-mail depois da validação: o banco barra e a view trata
        User.objects.create_user("ana", "ana@x.com", SENHA)
        with mock.patch.object(CadastroForm, "clean_email", lambda self: "ana@x.com"):
            r = self.client.post(self.url, dados(username="ana2", email="ana@x.com"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, ERRO)
        self.assertEqual(User.objects.count(), 1)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_corrida_entre_validacao_e_save(self):
        # O usuário concorrente é gravado logo depois da validação (fim do is_valid) e antes do save()
        original = CadastroForm._post_clean

        def post_clean_com_concorrente(form):
            original(form)
            User.objects.create_user("rival", "NOVO@exemplo.com", SENHA)

        with mock.patch.object(CadastroForm, "_post_clean", post_clean_com_concorrente):
            r = self.client.post(self.url, dados())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, ERRO)
        self.assertEqual(list(User.objects.values_list("username", flat=True)), ["rival"])

    def test_corrida_username_devolve_200_com_erro(self):
        User.objects.create_user("novo", "outro@exemplo.com", SENHA)
        with (mock.patch.object(CadastroForm, "clean_username", lambda self: "novo"),
              mock.patch.object(CadastroForm, "validate_unique", lambda self: None)):
            r = self.client.post(self.url, dados())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Já existe um usuário com este nome.")
        self.assertEqual(User.objects.filter(username="novo").count(), 1)


class IndiceEmailTest(TestCase):
    def test_orm_barra_email_em_outra_caixa(self):
        User.objects.create(username="a", email="Igual@X.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(username="b", email="igual@x.com")

    def test_email_vazio_pode_repetir(self):
        User.objects.create(username="a", email="")
        User.objects.create(username="b", email="")
        self.assertEqual(User.objects.filter(email="").count(), 2)


class AdminUsuarioTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("chefe", "chefe@nexar.com", SENHA)
        self.client.force_login(self.admin)
        self.ana = User.objects.create_user("ana", "ana@x.com", SENHA)

    def criar(self, **extra):
        d = {"username": "beto", "email": "beto@x.com", "usable_password": "true",
             "password1": SENHA, "password2": SENHA}
        d.update(extra)
        return self.client.post(reverse("admin:auth_user_add"), d)

    def editar(self, user, **extra):
        d = {"username": user.username, "email": user.email, "first_name": "", "last_name": "",
             "is_active": "on", "date_joined_0": "2026-01-01", "date_joined_1": "00:00:00"}
        d.update(extra)
        return self.client.post(reverse("admin:auth_user_change", args=[user.pk]), d)

    def test_criar_com_email_repetido(self):
        r = self.criar(email="ANA@x.com")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, ERRO)
        self.assertFalse(User.objects.filter(username="beto").exists())

    def test_criar_normaliza_e_aceita_vazio(self):
        r = self.criar(email="  Beto@X.com ")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(User.objects.get(username="beto").email, "beto@x.com")
        r = self.criar(username="semmail", email="")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(User.objects.get(username="semmail").email, "")

    def test_editar_com_email_de_outro(self):
        beto = User.objects.create_user("beto", "beto@x.com", SENHA)
        r = self.editar(beto, email="Ana@X.com")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, ERRO)
        beto.refresh_from_db()
        self.assertEqual(beto.email, "beto@x.com")

    def test_editar_mantendo_proprio_email(self):
        r = self.editar(self.ana, email="ANA@x.com", first_name="Ana")
        self.assertEqual(r.status_code, 302)
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.first_name, "Ana")
        self.assertEqual(self.ana.email, "ana@x.com")


class AdminPedidoTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("chefe", "chefe@nexar.com", SENHA)
        self.client.force_login(self.admin)
        cat = Categoria.objects.create(nome="Teste Email")
        self.produto = Produto.objects.create(nome="Peça", preco="49.90", categoria=cat)

    @staticmethod
    def itens(*linhas, iniciais=0):
        """Dados do formulário de itens (inline) do admin do pedido."""
        dados = {"itens-TOTAL_FORMS": len(linhas), "itens-INITIAL_FORMS": iniciais,
                 "itens-MIN_NUM_FORMS": 0, "itens-MAX_NUM_FORMS": 1000}
        for n, linha in enumerate(linhas):
            dados |= {f"itens-{n}-{campo}": valor for campo, valor in linha.items()}
        return dados

    def test_criacao_sem_preco_usa_preco_do_produto(self):
        r = self.client.post(reverse("admin:loja_pedido_add"), {"usuario": self.admin.pk} | self.itens(
            {"produto": self.produto.pk, "tamanho": "M", "quantidade": 2, "preco_unitario": ""}))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Pedido.objects.get().itens.get().preco_unitario, Decimal("49.90"))

    def test_edicao_preco_readonly(self):
        pedido = Pedido.com_item(self.produto, "M", usuario=self.admin)
        item = pedido.itens.get()
        url = reverse("admin:loja_pedido_change", args=[pedido.pk])
        formset = self.client.get(url).context["inline_admin_formsets"][0].formset
        self.assertNotIn("preco_unitario", formset.forms[0].fields)
        r = self.client.post(url, {"usuario": self.admin.pk} | self.itens(
            {"id": item.pk, "pedido": pedido.pk, "produto": self.produto.pk, "tamanho": "G", "quantidade": 3,
             "preco_unitario": "1.00"}, iniciais=1))
        self.assertEqual(r.status_code, 302)
        item.refresh_from_db()
        self.assertEqual((item.preco_unitario, item.quantidade), (Decimal("49.90"), 3))


class MigrationEmailUnicoTest(TransactionTestCase):
    antes = [("loja", "0004_pedido_preco_unitario")]
    depois = [("loja", "0005_email_unico")]

    def migrar(self, alvo):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(alvo)

    def tearDown(self):
        # limpa os dados de teste e volta o banco para o leaf (índice recriado).
        # Apaga com o User do estado atual das migrations: o User de hoje consulta colunas de Pedido
        # (entrega, frete...) que ainda não existem neste ponto do histórico.
        executor = MigrationExecutor(connection)
        atual = executor.loader.project_state(list(executor.loader.applied_migrations)).apps
        atual.get_model("auth", "User").objects.all().delete()
        self.migrar(MigrationExecutor(connection).loader.graph.leaf_nodes())

    def test_duplicados_barram_a_migration(self):
        self.migrar(self.antes)
        User.objects.create(username="a", email="Dup@Exemplo.com")
        User.objects.create(username="b", email="dup@exemplo.com")
        User.objects.create(username="c", email="")
        User.objects.create(username="d", email="")
        with self.assertRaisesMessage(Exception, "1 e-mail(s) repetido(s)") as ctx:
            self.migrar(self.depois)
        msg = str(ctx.exception)
        self.assertIn("d***@exemplo.com (2 contas)", msg)
        self.assertIn("em 2 contas", msg)
        self.assertNotIn("dup@", msg.lower())
        # nada foi alterado
        self.assertEqual(sorted(User.objects.values_list("email", flat=True)),
                         ["", "", "Dup@Exemplo.com", "dup@exemplo.com"])

    def test_sem_duplicados_cria_indice(self):
        self.migrar(self.antes)
        User.objects.create(username="a", email="um@x.com")
        User.objects.create(username="b", email="")
        User.objects.create(username="c", email="")
        self.migrar(self.depois)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(username="d", email="UM@x.com")


class EmailComEspacosTest(TestCase):
    """O índice e a validação comparam LOWER(TRIM(email)): espaços nas pontas não driblam a regra."""

    def test_indice_barra_email_com_espacos(self):
        from django.db import IntegrityError, transaction
        User.objects.create_user("um", email="a@x.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("dois", email=" A@x.com ")

    def test_cadastro_detecta_conta_antiga_com_espacos(self):
        # conta antiga gravada antes da normalização (sem passar pelo form): sem índice
        # ela não existiria junto de outra igual, mas pode ser a única com espaços
        User.objects.create_user("antiga", email="Ana@X.com ")
        r = self.client.post(reverse("loja:cadastro"), {
            "username": "nova", "email": "ana@x.com",
            "password1": "Nexar-teste-2026", "password2": "Nexar-teste-2026"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Já existe uma conta com este e-mail.")
        self.assertFalse(User.objects.filter(username="nova").exists())
