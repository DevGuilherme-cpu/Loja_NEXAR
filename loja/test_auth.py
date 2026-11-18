"""Testes de login, cadastro, logout e proteção do painel. Rodar com: python manage.py test loja"""
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import Categoria, Produto

SENHA = "Nexar-Senha-Forte-26"


class CadastroTest(TestCase):
    url = reverse("loja:cadastro")

    def dados(self, **extra):
        d = {"username": "cliente1", "email": "cliente1@exemplo.com", "password1": SENHA, "password2": SENHA}
        d.update(extra)
        return d

    def test_get_mostra_form(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'name="password2"')

    def test_cadastro_valido_cria_cliente_e_loga(self):
        r = self.client.post(self.url, self.dados())
        self.assertRedirects(r, reverse("loja:index"), fetch_redirect_response=False)
        u = User.objects.get(username="cliente1")
        self.assertEqual(u.email, "cliente1@exemplo.com")
        self.assertFalse(u.is_staff)
        self.assertFalse(u.is_superuser)
        self.assertEqual(int(self.client.session["_auth_user_id"]), u.pk)
        self.assertContains(self.client.get(reverse("loja:index")), "Conta criada!")

    def test_cadastro_nao_eleva_privilegio(self):
        self.client.post(self.url, self.dados(is_staff="on", is_superuser="on"))
        u = User.objects.get(username="cliente1")
        self.assertFalse(u.is_staff)
        self.assertFalse(u.is_superuser)

    def test_senhas_diferentes(self):
        r = self.client.post(self.url, self.dados(password2="Outra-Senha-99"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors.get("password2"))
        self.assertContains(r, 'class="erro"')
        self.assertFalse(User.objects.filter(username="cliente1").exists())

    def test_email_repetido_ignora_maiusculas(self):
        User.objects.create_user("outro", "Cliente1@Exemplo.com", SENHA)
        r = self.client.post(self.url, self.dados())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Já existe uma conta com este e-mail.")
        self.assertFalse(User.objects.filter(username="cliente1").exists())

    def test_username_repetido(self):
        User.objects.create_user("cliente1", "x@exemplo.com", SENHA)
        r = self.client.post(self.url, self.dados(email="novo@exemplo.com"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors.get("username"))
        self.assertEqual(User.objects.filter(username="cliente1").count(), 1)

    def test_email_obrigatorio(self):
        r = self.client.post(self.url, self.dados(email=""))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="cliente1").exists())

    def test_next_interno_e_externo(self):
        r = self.client.post(self.url, self.dados(next="/produtos/"))
        self.assertRedirects(r, "/produtos/")
        self.client.logout()
        r = self.client.post(self.url, self.dados(username="cliente2", email="c2@exemplo.com",
                                                  next="https://evil.com"))
        self.assertRedirects(r, reverse("loja:index"))

    def test_logado_vai_para_home(self):
        self.client.force_login(User.objects.create_user("ja", password=SENHA))
        self.assertRedirects(self.client.get(self.url), reverse("loja:index"))


class LoginLogoutTest(TestCase):
    url = reverse("loja:entrar")

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("maria", "maria@exemplo.com", SENHA)

    def test_login_correto(self):
        r = self.client.post(self.url, {"username": "maria", "password": SENHA})
        self.assertRedirects(r, reverse("loja:index"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_incorreto(self):
        r = self.client.post(self.url, {"username": "maria", "password": "errada"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'class="erro"')
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_next_interno_respeitado(self):
        r = self.client.post(self.url, {"username": "maria", "password": SENHA, "next": "/produtos/"})
        self.assertRedirects(r, "/produtos/")

    def test_next_externo_ignorado(self):
        for nxt in ["https://evil.com", "//evil.com/x"]:
            self.client.logout()
            r = self.client.post(self.url, {"username": "maria", "password": SENHA, "next": nxt})
            self.assertRedirects(r, reverse("loja:index"), msg_prefix=nxt)

    def test_fluxo_com_csrf_real(self):
        c = Client(enforce_csrf_checks=True)
        self.assertEqual(c.post(self.url, {"username": "maria", "password": SENHA}).status_code, 403)
        c.get(self.url)
        token = c.cookies["csrftoken"].value
        r = c.post(self.url, {"username": "maria", "password": SENHA, "csrfmiddlewaretoken": token})
        self.assertRedirects(r, reverse("loja:index"), fetch_redirect_response=False)
        token = c.cookies["csrftoken"].value  # o login gira o token
        r = c.post(reverse("loja:sair"), {"csrfmiddlewaretoken": token})
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("_auth_user_id", c.session)

    def test_logado_nao_ve_login(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(self.url), reverse("loja:index"))

    def test_logout_get_nao_desloga(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("loja:sair")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_post_desloga(self):
        self.client.force_login(self.user)
        r = self.client.post(reverse("loja:sair"))
        self.assertRedirects(r, reverse("loja:index"))
        self.assertNotIn("_auth_user_id", self.client.session)


class PainelProtegidoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = User.objects.create_user("cliente", password=SENHA)
        cls.staff = User.objects.create_user("equipe", password=SENHA, is_staff=True)
        cat = Categoria.objects.create(nome="Teste Auth")
        cls.cat_id = cat.id
        cls.prod_id = Produto.objects.create(nome="Peça Teste Auth", preco="10.00", categoria=cat).id

    def rotas_get(self):
        return [
            reverse("loja:painel_inicio"),
            reverse("loja:painel_produtos"),
            reverse("loja:painel_produto_novo"),
            reverse("loja:painel_produto_editar", args=[self.prod_id]),
            reverse("loja:painel_categorias"),
            reverse("loja:painel_pedidos"),
        ]

    def rotas_post(self):
        return [
            reverse("loja:painel_assistente"),
            reverse("loja:painel_produto_novo"),
            reverse("loja:painel_produto_editar", args=[self.prod_id]),
            reverse("loja:painel_produto_excluir", args=[self.prod_id]),
            reverse("loja:painel_categoria_nova"),
            reverse("loja:painel_categoria_editar", args=[self.cat_id]),
            reverse("loja:painel_categoria_excluir", args=[self.cat_id]),
        ]

    def test_visitante_vai_para_login(self):
        login = reverse("loja:entrar")
        for url in self.rotas_get():
            self.assertRedirects(self.client.get(url), f"{login}?next={url}", msg_prefix=url)
        for url in self.rotas_post():
            self.assertRedirects(self.client.post(url, {"nome": "x"}), f"{login}?next={url}", msg_prefix=url)

    def test_cliente_comum_bloqueado(self):
        self.client.force_login(self.cliente)
        for url in self.rotas_get():
            self.assertRedirects(self.client.get(url), reverse("loja:index"), msg_prefix=url)
        for url in self.rotas_post():
            self.assertRedirects(self.client.post(url, {"nome": "x"}), reverse("loja:index"), msg_prefix=url)
        r = self.client.get(reverse("loja:painel_produtos"), follow=True)
        self.assertContains(r, "Acesso restrito à equipe da loja.")

    def test_staff_acessa(self):
        self.client.force_login(self.staff)
        for url in self.rotas_get():
            self.assertEqual(self.client.get(url).status_code, 200, url)
        for url in self.rotas_post():
            r = self.client.post(url, {"nome": "x"})
            # staff chega na view: form com erros (200) ou volta para o painel (302) — nunca login/home
            self.assertIn(r.status_code, (200, 302), url)
            if r.status_code == 302:
                self.assertTrue(r.url.startswith("/painel/"), url)

    def test_mensagem_aparece_uma_vez_no_painel(self):
        self.client.force_login(self.staff)
        # categoria com produto: exclusão bloqueada, a mensagem aparece uma única vez
        r = self.client.post(reverse("loja:painel_categoria_excluir", args=[self.cat_id]), follow=True)
        self.assertEqual(r.content.decode().count("não pode ser excluída"), 1)


class MenuTest(TestCase):
    def test_visitante(self):
        html = self.client.get(reverse("loja:index")).content.decode()
        self.assertIn(f'href="{reverse("loja:entrar")}"', html)
        self.assertIn(f'href="{reverse("loja:cadastro")}"', html)
        self.assertNotIn(reverse("loja:sair"), html)
        self.assertNotIn(f'href="{reverse("loja:painel_inicio")}"', html)

    def test_cliente_ve_sair_sem_painel(self):
        self.client.force_login(User.objects.create_user("joana", password=SENHA))
        html = self.client.get(reverse("loja:index")).content.decode()
        self.assertIn(f'action="{reverse("loja:sair")}"', html)
        self.assertIn(">Sair</button>", html)
        self.assertIn("joana", html)
        self.assertNotIn(f'href="{reverse("loja:entrar")}"', html)
        self.assertNotIn(f'href="{reverse("loja:painel_inicio")}"', html)

    def test_staff_ve_painel(self):
        self.client.force_login(User.objects.create_user("chefe", password=SENHA, is_staff=True))
        html = self.client.get(reverse("loja:index")).content.decode()
        self.assertIn(">Sair</button>", html)
        self.assertIn(f'href="{reverse("loja:painel_inicio")}"', html)
