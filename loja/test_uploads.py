"""Uploads do painel no deploy: UPLOADS_HABILITADOS, falhas de gravação e URLs vindas do storage.

Rodar com: python manage.py test loja.test_uploads
Cada teste usa um MEDIA_ROOT temporário próprio (apagado no fim do teste).
"""
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage, default_storage
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import UPLOADS_DESATIVADOS
from .models import Categoria, Produto
from .test_crud import glb, png
from .views import link_arquivo


class MidiaTemporaria(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("equipe_upl", password="x", is_staff=True)
        cls.cat = Categoria.objects.create(nome="Cat Uploads")
        cls.prod = Produto.objects.create(
            nome="Produto Upl", descricao="d", preco=Decimal("50.00"), estoque=3, categoria=cls.cat,
            cor="#22306B", imagem="produtos/existente.jpg", imagem_2="produtos/existente2.jpg",
            modelo_3d="/static/modelos/tenis.glb",
        )

    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="nexar_test_upl_")
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        self.enterContext(override_settings(MEDIA_ROOT=self.media))
        self.client.force_login(self.staff)

    def arquivos(self):
        return sorted(p.name for p in Path(self.media).rglob("*") if p.is_file())

    def dados(self, **extra):
        d = {"nome": "Produto Upl", "descricao": "Nova descrição", "preco": "60.00", "estoque": "4",
             "categoria": str(self.cat.id), "cor": "#22306B"}
        d.update(extra)
        return d


@override_settings(UPLOADS_HABILITADOS=False)
class UploadsDesativadosTest(MidiaTemporaria):
    def test_recusa_arquivo_com_mensagem_e_nao_grava(self):
        novo = reverse("loja:painel_produto_novo")
        editar = reverse("loja:painel_produto_editar", args=[self.prod.id])
        for campo, arquivo in (("imagem", png), ("imagem_2", png), ("modelo_3d", glb)):
            for url in (novo, editar):
                with self.subTest(campo=campo, url=url):
                    antes = Produto.objects.count()
                    r = self.client.post(url, self.dados(nome="Outro nome", **{campo: arquivo()}))
                    self.assertEqual(r.status_code, 200)
                    self.assertContains(r, UPLOADS_DESATIVADOS)
                    self.assertEqual(Produto.objects.count(), antes)
                    self.assertEqual(self.arquivos(), [])
        self.prod.refresh_from_db()
        self.assertEqual(self.prod.nome, "Produto Upl")  # edição recusada não alterou nada

    def test_sem_arquivo_salva_e_preserva_existentes(self):
        r = self.client.post(reverse("loja:painel_produto_editar", args=[self.prod.id]),
                             self.dados(nome="Nome Editado"))
        self.assertRedirects(r, reverse("loja:painel_produtos"))
        self.prod.refresh_from_db()
        self.assertEqual(self.prod.nome, "Nome Editado")
        self.assertEqual(self.prod.preco, Decimal("60.00"))
        self.assertEqual(self.prod.imagem.name, "produtos/existente.jpg")
        self.assertEqual(self.prod.imagem_2.name, "produtos/existente2.jpg")
        self.assertEqual(self.prod.modelo_3d.name, "/static/modelos/tenis.glb")

    def test_novo_sem_arquivo_e_criado(self):
        r = self.client.post(reverse("loja:painel_produto_novo"), self.dados(nome="Sem anexos"))
        self.assertRedirects(r, reverse("loja:painel_produtos"))
        p = Produto.objects.get(nome="Sem anexos")
        self.assertFalse(p.imagem)
        self.assertFalse(p.modelo_3d)

    def test_template_mostra_aviso_e_desabilita_inputs(self):
        for url in (reverse("loja:painel_produto_novo"), reverse("loja:painel_produto_editar", args=[self.prod.id])):
            with self.subTest(url):
                r = self.client.get(url)
                self.assertContains(r, "Envio de arquivos desativado neste ambiente")
                self.assertContains(r, 'name="imagem" accept="image/*" disabled', html=False)
                self.assertContains(r, 'name="imagem_2" accept="image/*" disabled', html=False)
                self.assertContains(r, 'name="modelo_3d" accept=".glb,model/gltf-binary" disabled', html=False)


@override_settings(UPLOADS_HABILITADOS=True)
class UploadsHabilitadosTest(MidiaTemporaria):
    def test_template_sem_aviso_e_inputs_ativos(self):
        r = self.client.get(reverse("loja:painel_produto_novo"))
        self.assertNotContains(r, "Envio de arquivos desativado")
        self.assertNotContains(r, " disabled")

    def test_falha_do_storage_oserror(self):
        antes = Produto.objects.count()
        with mock.patch.object(FileSystemStorage, "_save", side_effect=OSError("disco cheio")):
            r = self.client.post(reverse("loja:painel_produto_novo"), self.dados(nome="Falha disco", imagem=png()))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Não foi possível gravar os arquivos enviados")
        self.assertNotContains(r, "cadastrado")
        self.assertEqual(Produto.objects.count(), antes)
        self.assertFalse(Produto.objects.filter(nome="Falha disco").exists())
        self.assertEqual(self.arquivos(), [])

    def test_erro_de_banco_no_save(self):
        antes = Produto.objects.count()
        with mock.patch.object(Produto, "save", side_effect=DatabaseError("conexão caiu")):
            r = self.client.post(reverse("loja:painel_produto_novo"), self.dados(nome="Falha banco"))
            r2 = self.client.post(reverse("loja:painel_produto_editar", args=[self.prod.id]),
                                  self.dados(nome="Falha banco 2"))
        for resp in (r, r2):
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, "Erro ao salvar no banco de dados")
            self.assertNotContains(resp, "atualizado")
        self.assertEqual(Produto.objects.count(), antes)
        self.prod.refresh_from_db()
        self.assertEqual(self.prod.nome, "Produto Upl")

    def test_upload_valido_continua_funcionando(self):
        r = self.client.post(reverse("loja:painel_produto_novo"), self.dados(nome="Com foto", imagem=png()))
        self.assertRedirects(r, reverse("loja:painel_produtos"))
        self.assertEqual(len(self.arquivos()), 1)


class LinkArquivoTest(TestCase):
    def test_nome_relativo_usa_o_storage(self):
        prod = Produto(imagem="produtos/x.jpg")
        with mock.patch.object(default_storage, "url", return_value="https://storage.exemplo/produtos/x.jpg") as url:
            self.assertEqual(link_arquivo(prod.imagem), ("x.jpg", "https://storage.exemplo/produtos/x.jpg"))
        url.assert_called_once_with("produtos/x.jpg")

    @override_settings(MEDIA_URL="https://cdn.exemplo/m/")
    def test_nome_relativo_segue_media_url_do_storage(self):
        self.assertEqual(link_arquivo(Produto(imagem="produtos/x.jpg").imagem)[1], "https://cdn.exemplo/m/produtos/x.jpg")

    def test_static_e_links_ficam_como_estao(self):
        for valor in ("/static/modelos/tenis.glb", "https://exemplo.com/a.glb", "http://exemplo.com/b.jpg"):
            with self.subTest(valor):
                self.assertEqual(link_arquivo(Produto(modelo_3d=valor).modelo_3d), (valor.rsplit("/", 1)[-1], valor))

    def test_vazio(self):
        self.assertIsNone(link_arquivo(Produto().imagem))


class RegraUploadsHabilitadosTest(TestCase):
    """loja.uploads.uploads_habilitados: usada pelo settings para definir UPLOADS_HABILITADOS."""

    def test_combinacoes(self):
        from .uploads import uploads_habilitados as f
        self.assertTrue(f(True, {}))                                   # desenvolvimento local
        self.assertFalse(f(False, {}))                                 # produção sem VERCEL exposta
        self.assertFalse(f(True, {"VERCEL": "1"}))                     # Vercel mesmo com DEBUG
        self.assertFalse(f(False, {"VERCEL": "1"}))
        self.assertTrue(f(False, {"UPLOADS_HABILITADOS": "True"}))     # variável explícita vence
        self.assertFalse(f(True, {"UPLOADS_HABILITADOS": "False"}))
        self.assertTrue(f(True, {"VERCEL": "1", "UPLOADS_HABILITADOS": "True"}))
