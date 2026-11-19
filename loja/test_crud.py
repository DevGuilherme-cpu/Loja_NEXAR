"""CRUD do painel (produtos, categorias e uploads). Rodar com: python manage.py test loja

Uploads vão para um MEDIA_ROOT temporário próprio de cada classe (apagado no fim). Ids sempre vêm do banco.
"""
import shutil
import tempfile
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Categoria, Pedido, Produto
from .test_glb import GLB_MINIMO  # GLB 2.0 válido gerado em código


def png(nome="foto.png", extra=0):
    buf = BytesIO()
    Image.new("RGB", (8, 8), (30, 40, 100)).save(buf, "PNG")
    return SimpleUploadedFile(nome, buf.getvalue() + b"\x00" * extra, content_type="image/png")


def glb(nome="peca.glb", conteudo=GLB_MINIMO):
    return SimpleUploadedFile(nome, conteudo, content_type="model/gltf-binary")


class CrudBase(TestCase):
    @classmethod
    def setUpClass(cls):
        # MEDIA_ROOT temporário exclusivo desta classe (cada subclasse ganha o seu)
        cls.media_temp = tempfile.mkdtemp(prefix="nexar_test_media_")
        cls._media_override = override_settings(MEDIA_ROOT=cls.media_temp)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls.media_temp, ignore_errors=True)

    def arquivos_em_media(self):
        raiz = Path(self.media_temp)
        return sorted(p.relative_to(raiz).as_posix() for p in raiz.rglob("*") if p.is_file())

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("equipe_crud", password="x", is_staff=True)
        cls.cliente = User.objects.create_user("cliente_crud", password="x")
        cls.cat = Categoria.objects.create(nome="Moletons CRUD")
        cls.cat2 = Categoria.objects.create(nome="Calças CRUD")
        cls.prod = Produto.objects.create(
            nome="Moletom Base", descricao="desc", preco=Decimal("199.90"), estoque=5, categoria=cls.cat,
            cor="#22306B", imagem="produtos/base.jpg", modelo_3d="/static/modelos/tenis.glb",
        )

    def setUp(self):
        shutil.rmtree(self.media_temp, ignore_errors=True)
        Path(self.media_temp).mkdir(parents=True, exist_ok=True)

    def dados(self, **extra):
        d = {"nome": "Camiseta Nova", "descricao": "Algodão", "preco": "89.90", "estoque": "7",
             "categoria": str(self.cat.id), "cor": "#1f2f6b"}
        d.update(extra)
        return d


class ProdutoCrudTest(CrudBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.staff)

    def test_cria_produto_completo_com_uploads(self):
        antes = Produto.objects.count()
        r = self.client.post(reverse("loja:painel_produto_novo"),
                             self.dados(imagem=png("frente.png"), imagem_2=png("costas.png"), modelo_3d=glb()),
                             follow=True)
        self.assertRedirects(r, reverse("loja:painel_produtos"))
        self.assertContains(r, "Produto “Camiseta Nova” cadastrado.")
        self.assertEqual(Produto.objects.count(), antes + 1)
        p = Produto.objects.get(nome="Camiseta Nova")
        self.assertEqual((p.preco, p.estoque, p.categoria_id, p.cor), (Decimal("89.90"), 7, self.cat.id, "#1F2F6B"))
        self.assertTrue(p.imagem.name.startswith("produtos/"))
        self.assertTrue(p.imagem_2.name.startswith("produtos/"))
        self.assertTrue(p.modelo_3d.name.startswith("modelos/") and p.modelo_3d.name.endswith(".glb"))
        for campo in (p.imagem, p.imagem_2, p.modelo_3d):
            self.assertTrue((Path(self.media_temp) / campo.name).is_file(), campo.name)

    def test_edicao_muda_nome_e_preco_e_mantem_arquivos(self):
        url = reverse("loja:painel_produto_editar", args=[self.prod.id])
        r = self.client.get(url)
        self.assertContains(r, 'value="Moletom Base"')
        self.assertContains(r, 'value="199.90"')
        self.assertContains(r, "tenis.glb")  # arquivo atual aparece
        r = self.client.post(url, self.dados(nome="Moletom Renomeado", preco="149.50"), follow=True)
        self.assertContains(r, "Produto “Moletom Renomeado” atualizado.")
        p = Produto.objects.get(id=self.prod.id)
        self.assertEqual((p.nome, p.preco), ("Moletom Renomeado", Decimal("149.50")))
        self.assertEqual(p.imagem.name, "produtos/base.jpg")
        self.assertEqual(p.modelo_3d.name, "/static/modelos/tenis.glb")
        self.assertEqual(self.arquivos_em_media(), [])

    def test_edicao_troca_modelo_enviado(self):
        url = reverse("loja:painel_produto_editar", args=[self.prod.id])
        self.client.post(url, self.dados(modelo_3d=glb("novo.glb")))
        p = Produto.objects.get(id=self.prod.id)
        self.assertTrue(p.modelo_3d.name.startswith("modelos/novo"))
        self.assertEqual(p.imagem.name, "produtos/base.jpg")

    def test_invalidos_nao_gravam_e_preservam_digitado(self):
        casos = {
            "preco negativo": (lambda: self.dados(preco="-1"), "maior ou igual a 0"),
            "estoque negativo": (lambda: self.dados(estoque="-3"), "maior ou igual a 0"),
            "nome vazio": (lambda: self.dados(nome="   "), "obrigatório"),
            "cor invalida": (lambda: self.dados(cor="azul"), "Cor inválida"),
            "categoria inexistente": (lambda: self.dados(categoria="999999999"), "Categoria inexistente"),
            "nao e imagem": (lambda: self.dados(imagem=SimpleUploadedFile("x.png", b"texto qualquer")), "não é uma imagem"),
            "imagem grande": (lambda: self.dados(imagem=png(extra=5 * 1024 * 1024)), "no máximo 5 MB"),
            "modelo extensao": (lambda: self.dados(modelo_3d=glb("peca.obj")), "arquivo .glb"),
            "modelo sem glTF": (lambda: self.dados(modelo_3d=glb("peca.glb", b"nada disso aqui")), "não é um glTF"),
        }
        antes = list(Produto.objects.values_list("id", "nome", "preco", "estoque"))
        for nome_caso, (dados, erro) in casos.items():
            with self.subTest(nome_caso):
                for url in (reverse("loja:painel_produto_novo"),
                            reverse("loja:painel_produto_editar", args=[self.prod.id])):
                    r = self.client.post(url, dados())
                    self.assertEqual(r.status_code, 200, url)
                    self.assertContains(r, erro)
                    self.assertContains(r, "Algodão")  # descrição digitada preservada
                    if nome_caso != "nome vazio":
                        self.assertContains(r, 'value="Camiseta Nova"')
                    self.assertEqual(list(Produto.objects.values_list("id", "nome", "preco", "estoque")), antes)
                    self.assertEqual(self.arquivos_em_media(), [])

    def test_valores_digitados_no_html(self):
        r = self.client.post(reverse("loja:painel_produto_novo"),
                             self.dados(preco="-5", estoque="12", categoria=str(self.cat2.id), cor="#ABCDEF"))
        html = r.content.decode()
        self.assertIn('value="-5"', html)
        self.assertIn('value="12"', html)
        self.assertIn('value="#ABCDEF"', html)
        self.assertIn(f'<option value="{self.cat2.id}" selected>', html)

    def test_excluir_sem_pedidos(self):
        p = Produto.objects.create(nome="Avulso", preco="10.00", categoria=self.cat)
        r = self.client.post(reverse("loja:painel_produto_excluir", args=[p.id]), follow=True)
        self.assertFalse(Produto.objects.filter(id=p.id).exists())
        self.assertContains(r, "Produto “Avulso” excluído.")

    def test_excluir_com_pedido_bloqueia(self):
        Pedido.com_item(self.prod, "M", 1, usuario=self.cliente)
        r = self.client.post(reverse("loja:painel_produto_excluir", args=[self.prod.id]), follow=True)
        self.assertTrue(Produto.objects.filter(id=self.prod.id).exists())
        self.assertContains(r, "tem 1 pedido(s) e não pode ser excluído")

    def test_404(self):
        inexistente = Produto.objects.order_by("-id").first().id + 1000
        self.assertEqual(self.client.post(reverse("loja:painel_produto_excluir", args=[inexistente])).status_code, 404)
        self.assertEqual(self.client.get(reverse("loja:painel_produto_editar", args=[inexistente])).status_code, 404)
        self.assertEqual(self.client.post(reverse("loja:painel_produto_editar", args=[inexistente]),
                                          self.dados()).status_code, 404)

    def test_mudar_preco_nao_altera_pedido_existente(self):
        pedido = Pedido.com_item(self.prod, "G", 2, usuario=self.cliente)
        self.assertEqual(pedido.itens.get().preco_unitario, Decimal("199.90"))
        self.client.post(reverse("loja:painel_produto_editar", args=[self.prod.id]), self.dados(preco="10.00"))
        self.assertEqual(Produto.objects.get(id=self.prod.id).preco, Decimal("10.00"))
        pedido = Pedido.objects.get(pk=pedido.pk)
        self.assertEqual(pedido.itens.get().preco_unitario, Decimal("199.90"))
        self.assertEqual(pedido.total, Decimal("399.80"))


class CategoriaCrudTest(CrudBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.staff)

    def test_criar(self):
        r = self.client.post(reverse("loja:painel_categoria_nova"), {"nome": "  Acessórios  "}, follow=True)
        self.assertTrue(Categoria.objects.filter(nome="Acessórios").exists())
        self.assertContains(r, "Categoria “Acessórios” criada.")

    def test_renomear(self):
        r = self.client.post(reverse("loja:painel_categoria_editar", args=[self.cat2.id]), {"nome": "Calças Wide"},
                             follow=True)
        self.assertEqual(Categoria.objects.get(id=self.cat2.id).nome, "Calças Wide")
        self.assertContains(r, "renomeada para “Calças Wide”")
        # mesmo nome com outra caixa na PRÓPRIA categoria é permitido
        self.client.post(reverse("loja:painel_categoria_editar", args=[self.cat2.id]), {"nome": "CALÇAS WIDE"})
        self.assertEqual(Categoria.objects.get(id=self.cat2.id).nome, "CALÇAS WIDE")

    def test_duplicada_outra_caixa(self):
        antes = list(Categoria.objects.values_list("id", "nome"))
        r = self.client.post(reverse("loja:painel_categoria_nova"), {"nome": "moletons crud"}, follow=True)
        self.assertContains(r, "Já existe uma categoria com este nome.")
        r = self.client.post(reverse("loja:painel_categoria_editar", args=[self.cat2.id]), {"nome": "MOLETONS CRUD"},
                             follow=True)
        self.assertContains(r, "Já existe uma categoria com este nome.")
        self.assertEqual(list(Categoria.objects.values_list("id", "nome")), antes)

    def test_nome_vazio(self):
        antes = Categoria.objects.count()
        r = self.client.post(reverse("loja:painel_categoria_nova"), {"nome": "   "}, follow=True)
        self.assertContains(r, "Categoria não salva")
        self.assertEqual(Categoria.objects.count(), antes)

    def test_excluir_vazia(self):
        vazia = Categoria.objects.create(nome="Vazia")
        r = self.client.post(reverse("loja:painel_categoria_excluir", args=[vazia.id]), follow=True)
        self.assertFalse(Categoria.objects.filter(id=vazia.id).exists())
        self.assertContains(r, "Categoria “Vazia” excluída.")

    def test_excluir_com_produtos_bloqueia(self):
        r = self.client.post(reverse("loja:painel_categoria_excluir", args=[self.cat.id]), follow=True)
        self.assertTrue(Categoria.objects.filter(id=self.cat.id).exists())
        self.assertContains(r, "tem 1 produto(s) e não pode ser excluída")

    def test_404(self):
        inexistente = Categoria.objects.order_by("-id").first().id + 1000
        self.assertEqual(self.client.post(reverse("loja:painel_categoria_excluir", args=[inexistente])).status_code, 404)
        self.assertEqual(self.client.post(reverse("loja:painel_categoria_editar", args=[inexistente]),
                                          {"nome": "X"}).status_code, 404)


class SemPermissaoTest(CrudBase):
    def estado(self):
        return (list(Produto.objects.values_list("id", "nome", "preco")),
                list(Categoria.objects.values_list("id", "nome")))

    def tentar_tudo(self):
        antes = self.estado()
        self.client.post(reverse("loja:painel_produto_novo"), self.dados(imagem=png()))
        self.client.post(reverse("loja:painel_produto_editar", args=[self.prod.id]), self.dados(preco="1.00"))
        self.client.post(reverse("loja:painel_produto_excluir", args=[self.prod.id]))
        self.client.post(reverse("loja:painel_categoria_nova"), {"nome": "Invasora"})
        self.client.post(reverse("loja:painel_categoria_editar", args=[self.cat.id]), {"nome": "Trocada"})
        self.client.post(reverse("loja:painel_categoria_excluir", args=[self.cat2.id]))
        self.assertEqual(self.estado(), antes)
        self.assertEqual(self.arquivos_em_media(), [])

    def test_visitante(self):
        self.tentar_tudo()

    def test_cliente_comum(self):
        self.client.force_login(self.cliente)
        self.tentar_tudo()


class CorAutomaticaEArquivosTest(TestCase):
    """Correções do QA: cor vazia não vira #22306B sozinha; sem 'limpar arquivo' por POST forjado."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import User
        cls.staff = User.objects.create_user("staff_cor", password="x", is_staff=True)
        cls.cat = Categoria.objects.create(nome="Cat Cor")

    def setUp(self):
        self.client.force_login(self.staff)

    def dados(self, prod, **extra):
        base = {"nome": prod.nome, "descricao": "", "preco": "10.00", "estoque": "1",
                "categoria": str(self.cat.id), "cor": "#22306B"}
        base.update(extra)
        return base

    def test_produto_sem_cor_continua_sem_cor_ao_editar(self):
        prod = Produto.objects.create(nome="Sem cor", preco="10.00", estoque=1, categoria=self.cat, cor="")
        url = reverse("loja:painel_produto_editar", args=[prod.id])
        self.assertContains(self.client.get(url), 'name="cor_automatica" checked')
        r = self.client.post(url, self.dados(prod, preco="12.00", cor_automatica="on"))
        self.assertEqual(r.status_code, 302)
        prod.refresh_from_db()
        self.assertEqual(prod.cor, "")
        self.assertEqual(str(prod.preco), "12.00")

    def test_desmarcar_automatica_grava_a_cor(self):
        prod = Produto.objects.create(nome="Vai ter cor", preco="10.00", estoque=1, categoria=self.cat, cor="")
        r = self.client.post(reverse("loja:painel_produto_editar", args=[prod.id]), self.dados(prod, cor="#aa00ff"))
        self.assertEqual(r.status_code, 302)
        prod.refresh_from_db()
        self.assertEqual(prod.cor, "#AA00FF")

    def test_post_forjado_nao_limpa_modelo(self):
        prod = Produto.objects.create(nome="Com modelo", preco="10.00", estoque=1, categoria=self.cat,
                                      cor="#111111", modelo_3d="/static/modelos/tenis.glb")
        self.client.post(reverse("loja:painel_produto_editar", args=[prod.id]),
                         self.dados(prod, cor="#111111", **{"modelo_3d-clear": "on"}))
        prod.refresh_from_db()
        self.assertEqual(prod.modelo_3d.name, "/static/modelos/tenis.glb")
