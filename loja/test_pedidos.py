"""Compra pela rota /pedido/: login, validação, estoque atômico, token anti-reenvio e preço histórico.

Rodar com: python manage.py test loja.test_pedidos
Ids sempre vêm do banco. O teste com threads reais só roda em PostgreSQL/MySQL (SQLite trava o arquivo).
"""
import threading
from decimal import Decimal
from unittest import mock, skipUnless

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.db import connection
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from .models import Categoria, Pedido, Produto

URL_PEDIDO = reverse("loja:pedido")


def criar_produto(estoque=5, preco="99.90", nome="Camiseta Teste Pedido"):
    categoria, _ = Categoria.objects.get_or_create(nome="Categoria Teste Pedidos")
    return Produto.objects.create(nome=nome, preco=Decimal(preco), estoque=estoque, categoria=categoria)


def mensagens(resposta):
    return [(m.level_tag, str(m)) for m in get_messages(resposta.wsgi_request)]


def pegar_token(client, produto):
    """Abre a página do produto (como o navegador faria) e devolve o token gerado na sessão."""
    resposta = client.get(reverse("loja:produto", args=[produto.id]))
    return resposta.context["token_pedido"]


class PedidoBase(TestCase):
    def setUp(self):
        self.produto = criar_produto()
        self.usuario = User.objects.create_user("cliente_pedido", password="senha-teste-123")
        self.client.force_login(self.usuario)
        self.url_produto = reverse("loja:produto", args=[self.produto.id])

    def comprar(self, token=None, **campos):
        dados = {"produto_id": self.produto.id, "tamanho": "M", "quantidade": "2",
                 "token_pedido": pegar_token(self.client, self.produto) if token is None else token}
        dados.update(campos)
        return self.client.post(URL_PEDIDO, {k: v for k, v in dados.items() if v is not None})

    def estoque(self):
        return Produto.objects.get(id=self.produto.id).estoque

    def assertNadaMudou(self, estoque=5):
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(self.estoque(), estoque)


class VisitanteTests(TestCase):
    def setUp(self):
        self.produto = criar_produto()

    def test_post_sem_login_vai_para_entrar_com_next(self):
        resposta = self.client.post(URL_PEDIDO, {"produto_id": self.produto.id, "tamanho": "M", "quantidade": "1"})
        url_produto = reverse("loja:produto", args=[self.produto.id])
        self.assertRedirects(resposta, f"{reverse('loja:entrar')}?next={url_produto}", fetch_redirect_response=False)
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(Produto.objects.get(id=self.produto.id).estoque, 5)
        self.assertTrue(any(nivel == "info" for nivel, _ in mensagens(resposta)))

    def test_get_em_pedido_e_405(self):
        self.assertEqual(self.client.get(URL_PEDIDO).status_code, 405)

    def test_pagina_do_produto_sem_token_para_visitante(self):
        resposta = self.client.get(reverse("loja:produto", args=[self.produto.id]))
        self.assertContains(resposta, f'action="{reverse("loja:checkout")}"')  # Comprar passa pelo checkout
        self.assertNotContains(resposta, 'name="token_pedido"')
        self.assertNotIn("token_pedido", resposta.context)


class CompraValidaTests(PedidoBase):
    def test_compra_cria_pedido_e_baixa_estoque(self):
        resposta = self.comprar(tamanho="G", quantidade="3")
        self.assertRedirects(resposta, self.url_produto, fetch_redirect_response=False)
        pedido = Pedido.objects.get()
        item = pedido.itens.get()
        self.assertEqual((pedido.usuario, item.produto_id, item.tamanho, item.quantidade),
                         (self.usuario, self.produto.id, "G", 3))
        self.assertEqual(item.preco_unitario, Decimal("99.90"))
        self.assertEqual(self.estoque(), 2)
        nivel, texto = mensagens(resposta)[-1]
        self.assertEqual(nivel, "success")
        self.assertIn(f"#{pedido.id}", texto)
        self.assertIn("R$ 299,70", texto)

    def test_compra_de_todo_o_estoque_zera(self):
        self.comprar(quantidade="5")
        self.assertEqual(self.estoque(), 0)
        self.assertEqual(Pedido.objects.count(), 1)

    def test_preco_historico_nao_muda(self):
        self.comprar(quantidade="1")
        Produto.objects.filter(id=self.produto.id).update(preco=Decimal("10.00"))
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.itens.get().preco_unitario, Decimal("99.90"))
        self.assertEqual(pedido.total, Decimal("99.90"))

    def test_preco_manipulado_no_post_e_ignorado(self):
        self.comprar(quantidade="1", preco="1", preco_unitario="0.01", personalizacao="cor=#000")
        self.assertEqual(Pedido.objects.get().itens.get().preco_unitario, Decimal("99.90"))

    def test_pagina_do_produto_tem_form_e_token_para_logado(self):
        resposta = self.client.get(self.url_produto)
        token = resposta.context["token_pedido"]
        self.assertContains(resposta, f'action="{reverse("loja:checkout")}"')  # Comprar passa pelo checkout
        self.assertContains(resposta, f'name="token_pedido" value="{token}"')
        self.assertContains(resposta, "csrfmiddlewaretoken")


class InvalidosTests(PedidoBase):
    def assertRecusado(self, resposta, destino=None):
        self.assertRedirects(resposta, destino or self.url_produto, fetch_redirect_response=False)
        self.assertTrue(any(n in ("error", "warning") for n, _ in mensagens(resposta)))
        self.assertNadaMudou()

    def test_produto_inexistente_404(self):
        id_livre = (Produto.objects.order_by("-id").values_list("id", flat=True).first() or 0) + 1000
        resposta = self.comprar(produto_id=id_livre)
        self.assertEqual(resposta.status_code, 404)
        self.assertNadaMudou()

    def test_produto_id_gigante_404(self):
        self.assertEqual(self.comprar(produto_id="9" * 9).status_code, 404)  # id válido mas inexistente
        self.assertNadaMudou()

    def test_produto_id_nao_numerico(self):
        for valor in ("abc", "", "-1", "1.5", "²", "١"):
            with self.subTest(valor=valor):
                self.assertRecusado(self.comprar(produto_id=valor), reverse("loja:produtos"))

    def test_tamanho_fora_da_lista(self):
        for valor in ("XG", "", "m", "PP"):
            with self.subTest(valor=valor):
                self.assertRecusado(self.comprar(tamanho=valor))

    def test_quantidade_invalida(self):
        for valor in ("0", "-1", "abc", "11", "2.5", "", "²", "١"):
            with self.subTest(valor=valor):
                self.assertRecusado(self.comprar(quantidade=valor))

    def test_quantidade_maior_que_estoque(self):
        resposta = self.comprar(quantidade="6")
        self.assertRecusado(resposta)
        self.assertIn("Só restam 5", mensagens(resposta)[-1][1])

    def test_produto_esgotado(self):
        Produto.objects.filter(id=self.produto.id).update(estoque=0)
        resposta = self.comprar(quantidade="1")
        self.assertRedirects(resposta, self.url_produto, fetch_redirect_response=False)
        self.assertEqual(mensagens(resposta)[-1], ("error", "Produto esgotado."))
        self.assertNadaMudou(estoque=0)

    def test_produto_excluido_no_meio_da_compra(self):
        fantasma = criar_produto(nome="Some no meio")
        Produto.objects.filter(id=fantasma.id).delete()
        with mock.patch("loja.views.get_object_or_404", return_value=fantasma):
            resposta = self.comprar(produto_id=fantasma.id, quantidade="1")
        self.assertRedirects(resposta, reverse("loja:produtos"), fetch_redirect_response=False)
        self.assertIn("não está mais disponível", mensagens(resposta)[-1][1])
        self.assertNadaMudou()


class TokenTests(PedidoBase):
    def test_reenvio_do_mesmo_token_nao_duplica(self):
        token = pegar_token(self.client, self.produto)
        self.comprar(token=token, quantidade="1")
        resposta = self.comprar(token=token, quantidade="1")
        self.assertEqual(Pedido.objects.count(), 1)
        self.assertEqual(self.estoque(), 4)
        self.assertEqual(mensagens(resposta)[-1][0], "warning")

    def test_token_ausente_ou_invalido(self):
        pegar_token(self.client, self.produto)
        for token in ("", "inventado", "0" * 32):
            with self.subTest(token=token):
                resposta = self.comprar(token=token)
                self.assertEqual(mensagens(resposta)[-1][0], "warning")
        resposta = self.client.post(URL_PEDIDO, {"produto_id": self.produto.id, "tamanho": "M", "quantidade": "1"})
        self.assertEqual(mensagens(resposta)[-1][0], "warning")
        self.assertNadaMudou()

    def test_token_de_outra_sessao_recusado(self):
        outro = Client()
        outro.force_login(User.objects.create_user("outro_cliente", password="senha-teste-123"))
        token_alheio = pegar_token(outro, self.produto)
        self.comprar(token=token_alheio)
        self.assertNadaMudou()

    def test_token_continua_valendo_apos_erro_de_validacao(self):
        token = pegar_token(self.client, self.produto)
        self.comprar(token=token, tamanho="XG")
        self.comprar(token=token, quantidade="0")
        self.assertNadaMudou()
        self.comprar(token=token, quantidade="1")
        self.assertEqual(Pedido.objects.count(), 1)

    def test_token_continua_valendo_apos_falta_de_estoque(self):
        token = pegar_token(self.client, self.produto)
        self.comprar(token=token, quantidade="9")
        self.assertNadaMudou()
        self.comprar(token=token, quantidade="5")
        self.assertEqual(Pedido.objects.count(), 1)
        self.assertEqual(self.estoque(), 0)


class CsrfTests(TestCase):
    def test_post_sem_csrf_e_403(self):
        produto = criar_produto()
        client = Client(enforce_csrf_checks=True)
        client.force_login(User.objects.create_user("cliente_csrf", password="senha-teste-123"))
        token = pegar_token(client, produto)
        resposta = client.post(URL_PEDIDO, {"produto_id": produto.id, "tamanho": "M", "quantidade": "1",
                                            "token_pedido": token})
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(Produto.objects.get(id=produto.id).estoque, 5)


class UltimaPecaSequencialTests(PedidoBase):
    """O UPDATE condicional (WHERE estoque >= q) impede vender a mesma última peça duas vezes."""

    def test_duas_compras_com_estoque_1(self):
        Produto.objects.filter(id=self.produto.id).update(estoque=1)
        outro = Client()
        outro.force_login(User.objects.create_user("cliente_2", password="senha-teste-123"))
        token_a = pegar_token(self.client, self.produto)
        token_b = pegar_token(outro, self.produto)  # os dois abriram a página com estoque 1
        self.comprar(token=token_a, quantidade="1")
        resposta = outro.post(URL_PEDIDO, {"produto_id": self.produto.id, "tamanho": "P",
                                           "quantidade": "1", "token_pedido": token_b})
        self.assertEqual(Pedido.objects.count(), 1)
        self.assertEqual(self.estoque(), 0)
        self.assertEqual(mensagens(resposta)[-1], ("error", "Produto esgotado."))


@skipUnless(connection.vendor in ("postgresql", "mysql"), "concorrência real exige PostgreSQL ou MySQL")
class UltimaPecaConcorrenteTests(TransactionTestCase):
    def test_duas_threads_disputam_a_ultima_peca(self):
        produto = criar_produto(estoque=1)
        clientes = []
        for i in range(2):
            client = Client()
            client.force_login(User.objects.create_user(f"thread_{i}", password="senha-teste-123"))
            clientes.append((client, pegar_token(client, produto)))

        barreira = threading.Barrier(2)
        status, erros = [], []

        def comprar(client, token):
            try:
                barreira.wait(timeout=10)
                resposta = client.post(URL_PEDIDO, {"produto_id": produto.id, "tamanho": "M",
                                                    "quantidade": "1", "token_pedido": token})
                status.append(resposta.status_code)
            except Exception as erro:  # noqa: BLE001 - repassado para a thread principal
                erros.append(erro)
            finally:
                connection.close()  # cada thread tem a sua conexão

        threads = [threading.Thread(target=comprar, args=par) for par in clientes]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertEqual(erros, [])
        self.assertEqual(status, [302, 302])
        self.assertEqual(Pedido.objects.filter(itens__produto=produto).count(), 1)
        self.assertEqual(Produto.objects.get(id=produto.id).estoque, 0)


class NumeroGiganteTests(PedidoBase):
    """QA: textos com milhares de dígitos não podem virar erro 500."""

    def test_quantidade_gigante(self):
        r = self.comprar(quantidade="9" * 5000)
        self.assertEqual(r.status_code, 302)
        self.assertNadaMudou()

    def test_produto_id_gigante(self):
        r = self.comprar(produto_id="9" * 5000)
        self.assertEqual(r.status_code, 302)
        self.assertNadaMudou()
