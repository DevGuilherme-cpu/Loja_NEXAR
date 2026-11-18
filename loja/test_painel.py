from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .assistente import responder
from .models import Categoria, Pedido, Produto
from .painel import reais


class PainelVisaoGeralTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat = Categoria.objects.create(nome="Camisetas Teste")
        cls.camiseta = Produto.objects.create(nome="Camiseta Teste", preco="100.00", estoque=2, categoria=cat)
        cls.moletom = Produto.objects.create(nome="Moletom Teste", preco="250.00", estoque=40, categoria=cat)
        cliente = User.objects.create_user("bia", password="x")
        Pedido.objects.create(usuario=cliente, produto=cls.camiseta, tamanho="M", quantidade=3,
                              preco_unitario=Decimal("100.00"))
        cls.staff = User.objects.create_user("chefe", password="x", is_staff=True)

    def test_reais(self):
        self.assertEqual(reais(Decimal("1234.5")), "R$ 1.234,50")
        self.assertEqual(reais(0), "R$ 0,00")

    def test_visao_geral_mostra_numeros(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("loja:painel_inicio"), {"dias": "7"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "R$ 300,00")
        self.assertEqual(r.context["dias"], 7)
        self.assertEqual(r.context["mais_vendidos"][0]["nome"], "Camiseta Teste")
        self.assertIn(self.camiseta, r.context["estoque_baixo"])
        # período fora da lista volta para 30 dias
        self.assertEqual(self.client.get(reverse("loja:painel_inicio"), {"dias": "999"}).context["dias"], 30)

    def test_assistente_responde_com_os_dados(self):
        self.assertIn("R$ 300,00", responder("Quanto vendi esta semana?"))
        self.assertIn("Camiseta Teste", responder("O que está acabando no estoque?"))
        self.assertIn("Camiseta Teste", responder("qual o produto MAIS vendido?"))
        self.assertIn("Moletom Teste", responder("quais produtos estão parados?"))
        self.assertIn("M", responder("tamanho mais vendido"))
        self.assertIn("Estoque atual: 40", responder("como está o moletom teste?"))
        self.assertIn("Não houve pedidos ontem", responder("quanto vendi ontem?"))
        self.assertIn("Ainda não sei", responder("qual a previsão do tempo?"))

    def test_assistente_json(self):
        self.client.force_login(self.staff)
        r = self.client.post(reverse("loja:painel_assistente"), {"pergunta": "ticket médio"},
                             headers={"X-Requested-With": "fetch"})
        self.assertEqual(r.json()["resposta"], "O ticket médio desde o início é R$ 300,00 (1 pedido).")


class MigrarTudoTest(TestCase):
    @mock.patch("subprocess.run")
    def test_roda_no_local_e_no_supabase(self, run):
        run.return_value.returncode = 0
        with mock.patch.dict("os.environ", {"SUPABASE_DATABASE_URL": "postgresql://supabase", "DATABASE_URL": "x"}):
            call_command("migrar_tudo", stdout=mock.Mock())
        local, supabase = (c.kwargs["env"] for c in run.call_args_list)
        self.assertNotIn("DATABASE_URL", local)  # local nunca herda a URL do Supabase
        self.assertEqual(supabase["DATABASE_URL"], "postgresql://supabase")

    @mock.patch("subprocess.run")
    def test_para_se_o_local_falhar(self, run):
        run.return_value.returncode = 1
        with mock.patch.dict("os.environ", {"SUPABASE_DATABASE_URL": "postgresql://supabase"}):
            with self.assertRaises(Exception):
                call_command("migrar_tudo", stdout=mock.Mock())
        self.assertEqual(run.call_count, 1)
