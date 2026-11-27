"""Painel de gestão: login da equipe vai ao painel, grupos Clientes/Funcionários, Finanças, Estoque e Clientes."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .grupos import CLIENTES, FUNCIONARIOS
from .models import Categoria, Pedido, Produto

SENHA = "Nexar-teste-2026"


def grupos(usuario):
    return sorted(usuario.groups.values_list("name", flat=True))


class LoginEGruposTest(TestCase):
    def test_equipe_entra_no_painel_e_cliente_na_loja(self):
        User.objects.create_user("chefe", password=SENHA, is_staff=True)
        User.objects.create_user("bia", password=SENHA)
        r = self.client.post(reverse("loja:entrar"), {"username": "chefe", "password": SENHA})
        self.assertRedirects(r, reverse("loja:painel_inicio"), fetch_redirect_response=False)
        self.client.logout()
        r = self.client.post(reverse("loja:entrar"), {"username": "bia", "password": SENHA})
        self.assertNotEqual(r.url, reverse("loja:painel_inicio"))
        # com "next" (ex.: vindo do checkout) o destino pedido continua valendo, até para a equipe
        self.client.logout()
        r = self.client.post(f"{reverse('loja:entrar')}?next={reverse('loja:sacola')}",
                             {"username": "chefe", "password": SENHA})
        self.assertRedirects(r, reverse("loja:sacola"), fetch_redirect_response=False)

    def test_cada_usuario_fica_no_grupo_certo(self):
        self.client.post(reverse("loja:cadastro"), {"username": "nova", "email": "nova@exemplo.com",
                                                    "password1": SENHA, "password2": SENHA})
        self.assertEqual(grupos(User.objects.get(username="nova")), [CLIENTES])
        chefe = User.objects.create_user("chefe", password=SENHA, is_staff=True)
        self.assertEqual(grupos(chefe), [FUNCIONARIOS])
        # promovido a funcionário: troca de grupo; deixa de ser: volta a cliente
        bia = User.objects.create_user("bia", password=SENHA)
        bia.is_staff = True
        bia.save()
        self.assertEqual(grupos(bia), [FUNCIONARIOS])
        bia.is_staff = False
        bia.save()
        self.assertEqual(grupos(bia), [CLIENTES])

    def test_cliente_nao_abre_as_paginas_novas(self):
        self.client.force_login(User.objects.create_user("bia", password=SENHA))
        for nome in ("loja:painel_financas", "loja:painel_clientes"):
            self.assertRedirects(self.client.get(reverse(nome)), reverse("loja:index"), fetch_redirect_response=False)


class GestaoBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat = Categoria.objects.create(nome="Camisetas Gestão")
        cls.camiseta = Produto.objects.create(nome="Camiseta G", preco=Decimal("100.00"), estoque=4, categoria=cat)
        cls.bone = Produto.objects.create(nome="Boné G", preco=Decimal("50.00"), estoque=0, categoria=cat)
        cls.ana = User.objects.create_user("ana", password=SENHA)
        cls.beto = User.objects.create_user("beto", password=SENHA)
        cls.chefe = User.objects.create_user("chefe", password=SENHA, is_staff=True)
        # ana: 2 pedidos (300 + 19,90 de frete e 100); beto: 1 pedido de 50; visitante: 1 de 200
        Pedido.com_item(cls.camiseta, "M", 3, usuario=cls.ana, pagamento="pix", envio="padrao", frete=Decimal("19.90"))
        Pedido.com_item(cls.camiseta, "G", 1, usuario=cls.ana, pagamento="cartao", envio="expresso")
        Pedido.com_item(cls.bone, "U", 1, usuario=cls.beto)
        Pedido.com_item(cls.camiseta, "P", 2, entrega_nome="Caio", entrega_email="caio@exemplo.com", pagamento="pix")

    def setUp(self):
        self.client.force_login(self.chefe)


class FinancasTest(GestaoBase):
    def test_totais_e_formas_de_pagamento(self):
        r = self.client.get(reverse("loja:painel_financas"), {"dias": "7"})
        self.assertEqual(r.status_code, 200)
        kpis = {k["nome"]: k["valor"] for k in r.context["kpis"]}
        # peças 300 + 100 + 50 + 200 = 650; frete 19,90
        self.assertEqual(kpis["Venda de peças"], "R$ 650,00")
        self.assertEqual(kpis["Fretes cobrados"], "R$ 19,90")
        self.assertEqual(kpis["Total recebido"], "R$ 669,90")
        pagamentos = {b["nome"]: b["texto"] for b in r.context["por_pagamento"]}
        self.assertEqual(pagamentos, {"Pix": "R$ 519,90", "Cartão": "R$ 100,00", "Sem checkout": "R$ 50,00"})
        self.assertEqual(len(r.context["mensal"]), 6)
        self.assertEqual(r.context["mensal"][-1]["texto"], "R$ 669,90")  # mês atual


class EstoqueTest(GestaoBase):
    def repor(self, produto, quantidade):
        return self.client.post(reverse("loja:painel_estoque_repor", args=[produto.id]), {"quantidade": quantidade})

    def test_resumo_do_estoque(self):
        r = self.client.get(reverse("loja:painel_produtos"))
        self.assertContains(r, "<h1>Estoque</h1>", html=True)
        self.assertEqual((r.context["estoque_pecas"], r.context["estoque_esgotados"], r.context["estoque_baixo"]),
                         (4, 1, 1))
        self.assertEqual(r.context["estoque_valor"], "R$ 400,00")  # 4 x 100; o boné esgotado vale 0

    def test_repor_soma_ao_estoque(self):
        r = self.repor(self.bone, "12")
        self.assertRedirects(r, f"{reverse('loja:painel_produtos')}#produto-{self.bone.id}",
                             fetch_redirect_response=False)
        self.assertEqual(Produto.objects.get(pk=self.bone.pk).estoque, 12)

    def test_repor_recusa_valores_invalidos(self):
        for valor in ("0", "-5", "abc", "1000", "", "2.5"):
            with self.subTest(valor=valor):
                self.repor(self.camiseta, valor)
                self.assertEqual(Produto.objects.get(pk=self.camiseta.pk).estoque, 4)

    def test_so_a_equipe_repoe_e_so_por_post(self):
        self.assertEqual(self.client.get(reverse("loja:painel_estoque_repor", args=[self.bone.id])).status_code, 405)
        self.client.force_login(self.ana)
        self.repor(self.bone, "5")
        self.assertEqual(Produto.objects.get(pk=self.bone.pk).estoque, 0)


class ClientesTest(GestaoBase):
    def test_ranking_de_quem_mais_compra(self):
        r = self.client.get(reverse("loja:painel_clientes"))
        ranking = [(c["nome"], c["pedidos"], c["texto"]) for c in r.context["ranking"]]
        self.assertEqual(ranking, [("ana", 2, "R$ 419,90"), ("Caio (visitante)", 1, "R$ 200,00"), ("beto", 1, "R$ 50,00")])
        self.assertEqual(r.context["total_clientes"], 2)  # ana e beto; o chefe é Funcionários
        self.assertEqual([u.username for u in r.context["equipe"]], ["chefe"])
        self.assertContains(r, "Visitante")
