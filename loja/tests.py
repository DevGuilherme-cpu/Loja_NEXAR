from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from .models import Categoria, Pedido, Produto


class LojaTest(TestCase):
    """Rodar com: python manage.py test loja

    Os ids vêm do banco (nunca fixos): no MySQL/PostgreSQL o auto-increment não volta a 1 entre testes.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("popular_loja", verbosity=0)

    def test_dados_de_exemplo_cumprem_minimo_de_5(self):
        self.assertGreaterEqual(Categoria.objects.count(), 5)
        self.assertGreaterEqual(Produto.objects.count(), 5)
        self.assertGreaterEqual(Pedido.objects.count(), 5)

    def entrar_como_staff(self):
        self.client.force_login(User.objects.create_user("equipe", password="x", is_staff=True))

    def test_paginas_abrem(self):
        primeiro = Produto.objects.first().id
        for url in ["/", "/produtos/", f"/produto/{primeiro}/", "/entrar/", "/cadastro/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.get("/produto/999999/").status_code, 404)

    def test_painel_so_para_admin(self):
        primeiro = Produto.objects.first().id
        urls = ["/painel/", "/painel/categorias/", "/painel/pedidos/", f"/painel/produtos/{primeiro}/editar/"]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302, url)  # visitante vai para o login
        self.entrar_como_staff()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_3d_recebe_cor_do_produto(self):
        moletom = Produto.objects.get(nome="Moletom Heavy")
        html = self.client.get(f"/produto/{moletom.id}/").content.decode()
        self.assertIn('data-cor="#22306B"', html)
        self.assertIn(f"view-transition-name: produto-{moletom.id}", html)

    def test_busca_e_filtro(self):
        r = self.client.get("/produtos/", {"busca": "moletom"})
        self.assertEqual([p.nome for p in r.context["produtos"]], ["Moletom Heavy", "Moletom Drop 01"])
        calcas = Categoria.objects.get(nome="Calças")
        r = self.client.get("/produtos/", {"categoria": str(calcas.id)})
        nomes = [p.nome for p in r.context["produtos"]]
        self.assertEqual(nomes, ["Calça Cargo Tech", "Calça Wide Denim"])  # lista vazia também falharia
        r = self.client.get("/produtos/", {"categoria": "abc"})  # lixo na URL não quebra a página
        self.assertEqual(r.status_code, 200)

    def test_pedidos_mostram_join(self):
        self.entrar_como_staff()
        html = self.client.get("/painel/pedidos/").content.decode()
        self.assertIn("ana.souza", html)
        self.assertIn("R$ 449,70", html)  # 3 x 149,90 gravado em preco_unitario
