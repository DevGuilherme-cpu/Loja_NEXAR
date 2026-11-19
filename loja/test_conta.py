from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Categoria, Pedido, Produto

SENHA = "senha-de-teste-123"


class TamanhosTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        acessorios = Categoria.objects.create(nome="Acessórios")
        cls.tenis = Produto.objects.create(nome="Tênis Runner X", preco="699.90", estoque=5, categoria=acessorios)
        cls.oculos = Produto.objects.create(nome="Óculos Shade", preco="259.90", estoque=5, categoria=acessorios)
        cls.camiseta = Produto.objects.create(nome="Camiseta Grid", preco="159.90", estoque=5,
                                              categoria=Categoria.objects.create(nome="Camisetas"))
        cls.calca = Produto.objects.create(nome="Calça Cargo", preco="349.90", estoque=5,
                                           categoria=Categoria.objects.create(nome="Calças"))

    def test_grade_pelo_tipo_de_produto(self):
        self.assertEqual(self.tenis.tamanhos, ["38", "39", "40", "41", "42", "43", "44"])
        self.assertEqual(self.oculos.tamanhos, ["U"])
        self.assertEqual(self.camiseta.tamanhos, ["P", "M", "G", "GG"])
        self.assertEqual(self.calca.grade, "calca")

    def test_pagina_mostra_os_tamanhos_certos(self):
        html = self.client.get(reverse("loja:produto", args=[self.tenis.id])).content.decode()
        self.assertIn('value="42"', html)
        self.assertNotIn('value="GG"', html)
        self.assertIn("Guia de medidas", html)
        html = self.client.get(reverse("loja:produto", args=[self.oculos.id])).content.decode()
        self.assertIn("Tamanho único", html)
        self.assertIn("art. 49", html)  # direito de arrependimento visível

    def test_pedido_recusa_tamanho_de_outra_grade(self):
        self.client.force_login(User.objects.create_user("bia", password=SENHA))
        url = reverse("loja:produto", args=[self.tenis.id])
        self.client.get(url)
        token = self.client.session["pedido_tokens"][-1]
        dados = {"produto_id": self.tenis.id, "quantidade": "1", "token_pedido": token}
        self.client.post(reverse("loja:pedido"), dados | {"tamanho": "M"})
        self.assertFalse(Pedido.objects.exists())
        self.client.post(reverse("loja:pedido"), dados | {"tamanho": "41"})
        self.assertEqual(Pedido.objects.get().itens.get().tamanho, "41")


class EncerrarContaTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("joana", email="joana@exemplo.com", password=SENHA)
        self.client.force_login(self.usuario)

    def encerrar(self, senha=SENHA):
        return self.client.post(reverse("loja:conta_encerrar"), {"senha": senha}, follow=True)

    def test_minha_conta_abre_e_exige_login(self):
        self.assertContains(self.client.get(reverse("loja:conta")), "Encerrar minha conta")
        self.client.logout()
        self.assertEqual(self.client.get(reverse("loja:conta")).status_code, 302)

    def test_senha_errada_nao_encerra(self):
        r = self.encerrar("errada")
        self.assertContains(r, "Senha incorreta")
        self.assertTrue(User.objects.filter(pk=self.usuario.pk, is_active=True).exists())

    def test_sem_pedidos_apaga_a_conta(self):
        r = self.encerrar()
        self.assertContains(r, "Protocolo NX-")
        self.assertFalse(User.objects.filter(pk=self.usuario.pk).exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_com_pedidos_anonimiza_e_mantem_o_pedido(self):
        cat = Categoria.objects.create(nome="Camisetas")
        produto = Produto.objects.create(nome="Camiseta", preco="100.00", categoria=cat)
        pedido = Pedido.com_item(produto, "M", 1, Decimal("100.00"), usuario=self.usuario)
        self.encerrar()
        u = User.objects.get(pk=self.usuario.pk)
        self.assertEqual((u.username, u.email, u.is_active, u.has_usable_password()),
                         (f"conta-encerrada-{u.pk}", "", False, False))
        self.assertTrue(Pedido.objects.filter(pk=pedido.pk).exists())

    def test_equipe_nao_encerra_pelo_site(self):
        self.usuario.is_staff = True
        self.usuario.save()
        r = self.encerrar()
        self.assertContains(r, "Contas da equipe")
        self.assertTrue(User.objects.filter(pk=self.usuario.pk, is_active=True).exists())
