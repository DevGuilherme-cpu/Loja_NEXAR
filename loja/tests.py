from django.core.management import call_command
from django.test import TestCase

from .models import Categoria, Pedido, Produto


class LojaTest(TestCase):
    """Rodar com: python manage.py test loja"""

    @classmethod
    def setUpTestData(cls):
        call_command("popular_loja", verbosity=0)

    def test_dados_de_exemplo_cumprem_minimo_de_5(self):
        self.assertGreaterEqual(Categoria.objects.count(), 5)
        self.assertGreaterEqual(Produto.objects.count(), 5)
        self.assertGreaterEqual(Pedido.objects.count(), 5)

    def entrar_como_admin(self):
        from django.contrib.auth.models import User
        self.client.force_login(User.objects.create_user("admin_teste", is_staff=True))

    def test_paginas_abrem(self):
        for url in ["/", "/produtos/", "/produto/1/", "/entrar/", "/cadastro/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.get("/produto/999/").status_code, 404)

    def test_painel_so_para_admin(self):
        for url in ["/painel/", "/painel/categorias/", "/painel/pedidos/", "/painel/produtos/1/editar/"]:
            self.assertEqual(self.client.get(url).status_code, 302, url)  # manda para o login
        self.entrar_como_admin()
        for url in ["/painel/", "/painel/categorias/", "/painel/pedidos/", "/painel/produtos/1/editar/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_3d_recebe_cor_do_produto(self):
        html = self.client.get("/produto/3/").content.decode()
        self.assertIn('data-cor="#22306B"', html)
        self.assertIn("view-transition-name: produto-3", html)

    def test_busca_e_filtro(self):
        r = self.client.get("/produtos/", {"busca": "moletom"})
        self.assertEqual([p.nome for p in r.context["produtos"]], ["Moletom Heavy", "Moletom Drop 01"])
        r = self.client.get("/produtos/", {"categoria": "3"})
        self.assertTrue(all(p.categoria.nome == "Calças" for p in r.context["produtos"]))
        r = self.client.get("/produtos/", {"categoria": "abc"})  # lixo na URL não quebra a página
        self.assertEqual(r.status_code, 200)

    def test_pedidos_mostram_join(self):
        self.entrar_como_admin()
        html = self.client.get("/painel/pedidos/").content.decode()
        self.assertIn("ana.souza", html)
        self.assertIn("R$ 449,70", html)  # 3 x 149,90 calculado pelo total do model
