from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import cpf_valido
from .models import Categoria, Pedido, Produto

CPF_OK = "529.982.247-25"  # CPF de exemplo com dígitos verificadores válidos


class CheckoutTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat = Categoria.objects.create(nome="Camisetas")
        cls.produto = Produto.objects.create(nome="Camiseta Grid", preco=Decimal("159.90"), estoque=5, categoria=cat)
        cls.usuario = User.objects.create_user("bia", password="senha-teste-123")

    def escolher(self, tamanho="M", quantidade="1"):
        return self.client.post(reverse("loja:checkout"),
                                {"produto_id": self.produto.id, "tamanho": tamanho, "quantidade": quantidade})

    def entrega(self, **mudar):
        dados = {"checkout": "1", "produto_id": self.produto.id, "tamanho": "M", "quantidade": "1",
                 "token_pedido": self.client.get(reverse("loja:checkout")).context["token_pedido"],
                 "nome": "Bia Souza", "cpf": CPF_OK, "telefone": "(11) 91234-5678", "cep": "01310-100",
                 "endereco": "Av. Paulista", "numero": "1000", "complemento": "", "bairro": "Bela Vista",
                 "cidade": "São Paulo", "uf": "SP", "envio": "padrao", "pagamento": "pix"}
        dados.update(mudar)
        return self.client.post(reverse("loja:pedido"), dados)

    def test_cpf(self):
        self.assertTrue(cpf_valido("52998224725"))
        self.assertFalse(cpf_valido("52998224724"))
        self.assertFalse(cpf_valido("11111111111"))

    def test_visitante_vai_ao_checkout_sem_login(self):
        r = self.escolher()
        self.assertRedirects(r, reverse("loja:checkout"), fetch_redirect_response=False)
        r = self.client.get(reverse("loja:checkout"))
        self.assertContains(r, "Camiseta Grid")
        self.assertContains(r, "Comprando sem conta")
        self.assertContains(r, 'name="email"')
        # se preferir entrar, a escolha continua na sessão depois do login
        self.client.force_login(self.usuario)
        r = self.client.get(reverse("loja:checkout"))
        self.assertContains(r, "Camiseta Grid")
        self.assertNotContains(r, "Comprando sem conta")

    def test_visitante_precisa_de_email(self):
        self.escolher()
        r = self.entrega(email="")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Este campo é obrigatório")
        self.assertFalse(Pedido.objects.exists())

    def test_compra_sem_conta_e_link_secreto(self):
        self.escolher()
        r = self.entrega(email="Bia@Exemplo.com")
        pedido = Pedido.objects.get()
        self.assertIsNone(pedido.usuario)
        self.assertEqual(pedido.entrega_email, "bia@exemplo.com")
        self.assertGreaterEqual(len(pedido.codigo), 20)
        link = reverse("loja:pedido_acompanhar", args=[pedido.codigo])
        self.assertRedirects(r, link, fetch_redirect_response=False)
        self.assertEqual(Produto.objects.get(pk=self.produto.pk).estoque, 4)
        # o link abre sem login; código errado ou o número do pedido não abrem
        pagina = self.client.get(link)
        self.assertContains(pagina, "Guarde este link")
        self.assertContains(pagina, "Acompanhe a entrega")
        self.assertEqual(self.client.get(reverse("loja:pedido_acompanhar", args=["codigo-errado"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("loja:pedido_confirmado", args=[pedido.id])).status_code, 302)

    def test_animacao_da_caixa_toca_uma_vez_so(self):
        self.client.force_login(self.usuario)
        self.escolher(quantidade="2")
        r = self.entrega(quantidade="2")
        primeira = self.client.get(r.url)
        self.assertContains(primeira, 'id="anim-pedido"')
        self.assertContains(primeira, "2 peças")
        self.assertContains(primeira, "Acompanhar meu pedido")
        # atualizar a página não repete a animação; a confirmação continua lá
        segunda = self.client.get(r.url)
        self.assertNotContains(segunda, 'id="anim-pedido"')
        self.assertContains(segunda, "Pedido confirmado")

    def test_formulario_com_erro_nao_anima(self):
        self.client.force_login(self.usuario)
        self.escolher()
        self.entrega(cpf="123")
        self.assertNotIn("animar_pedido", self.client.session)

    def test_compra_direta_sem_checkout_ainda_exige_conta(self):
        r = self.client.post(reverse("loja:pedido"), {"produto_id": self.produto.id, "tamanho": "M", "quantidade": "1"})
        self.assertTrue(r.url.startswith(reverse("loja:entrar")))
        self.assertFalse(Pedido.objects.exists())

    def test_painel_mostra_pedido_de_visitante(self):
        self.escolher()
        self.entrega(email="bia@exemplo.com")
        self.client.force_login(User.objects.create_user("chefe", password="senha-teste-123", is_staff=True))
        for url in (reverse("loja:painel_pedidos"), reverse("loja:painel_inicio")):
            self.assertContains(self.client.get(url), "Bia Souza (visitante)")

    def test_comprar_na_pagina_do_produto_vai_ao_checkout_sem_gravar(self):
        self.client.force_login(self.usuario)
        html = self.client.get(reverse("loja:produto", args=[self.produto.id])).content.decode()
        self.assertIn(f'class="pdp-form" method="post" action="{reverse("loja:checkout")}"', html)
        r = self.escolher()  # o mesmo POST que o botão Comprar faz
        self.assertRedirects(r, reverse("loja:checkout"), fetch_redirect_response=False)
        self.assertFalse(Pedido.objects.exists())

    def test_tamanho_invalido_volta_ao_produto(self):
        self.client.force_login(self.usuario)
        self.escolher(tamanho="42")
        r = self.client.get(reverse("loja:checkout"))
        self.assertRedirects(r, reverse("loja:produto", args=[self.produto.id]), fetch_redirect_response=False)

    def test_dados_invalidos_mostram_erros_e_nao_gravam(self):
        self.client.force_login(self.usuario)
        self.escolher()
        r = self.entrega(cpf="123.456.789-00", cep="123")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "CPF inválido")
        self.assertContains(r, "O CEP tem 8 números")
        self.assertFalse(Pedido.objects.exists())
        self.assertEqual(Produto.objects.get(pk=self.produto.pk).estoque, 5)

    def test_compra_completa_grava_entrega_com_cpf_mascarado(self):
        self.client.force_login(self.usuario)
        self.escolher(quantidade="2")
        r = self.entrega(quantidade="2", envio="padrao")
        pedido = Pedido.objects.get()
        self.assertRedirects(r, reverse("loja:pedido_confirmado", args=[pedido.id]), fetch_redirect_response=False)
        self.assertEqual(pedido.entrega_cpf, "***.***.***-25")
        self.assertNotIn("52998224725", str(Pedido.objects.values().get()))  # CPF completo não é gravado
        self.assertEqual((pedido.entrega_cep, pedido.entrega_uf, pedido.pagamento), ("01310-100", "SP", "pix"))
        self.assertEqual(pedido.frete, Decimal("0"))  # 2 x 159,90 passa de R$ 300: padrão grátis
        self.assertEqual(Produto.objects.get(pk=self.produto.pk).estoque, 3)
        pagina = self.client.get(r.url)
        self.assertContains(pagina, "Pedido confirmado")
        self.assertContains(pagina, "R$ 319,80")
        # rastreio: recém-comprado está separando, e o mapa vai até a cidade do cliente
        self.assertEqual(pagina.context["etapa"], 2)
        self.assertEqual(pagina.context["entregas"][0]["cidade"], "São Paulo")
        self.assertContains(pagina, "Acompanhe a entrega")
        self.assertContains(self.client.get(reverse("loja:conta")), "Acompanhar entrega")

    def test_expresso_cobra_e_padrao_abaixo_de_300_cobra(self):
        self.client.force_login(self.usuario)
        self.escolher()
        self.entrega(envio="expresso")
        self.assertEqual(Pedido.objects.get().frete, Decimal("34.90"))
        Pedido.objects.all().delete()
        Produto.objects.filter(pk=self.produto.pk).update(estoque=5)
        self.escolher()
        self.entrega()
        self.assertEqual(Pedido.objects.get().frete, Decimal("19.90"))

    def test_confirmacao_so_para_o_dono(self):
        self.client.force_login(self.usuario)
        self.escolher()
        self.entrega()
        pedido = Pedido.objects.get()
        self.client.force_login(User.objects.create_user("outro", password="senha-teste-123"))
        self.assertEqual(self.client.get(reverse("loja:pedido_confirmado", args=[pedido.id])).status_code, 404)
