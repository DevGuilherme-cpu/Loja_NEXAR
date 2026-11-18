"""Nome de categoria único sem diferenciar caixa (índice da 0006), corrida no painel e mídia isolada.

Regra: colidem os nomes com o mesmo LOWER(TRIM(nome)). Acentos e espaços internos contam.
Rodar com: python manage.py test loja
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .forms import CATEGORIA_REPETIDA, CategoriaForm
from .models import Categoria

INDICE = "categorias_nome_ci_uniq"


def indices_categorias():
    with connection.cursor() as cursor:
        return set(connection.introspection.get_constraints(cursor, "categorias"))


class IndiceCategoriaTest(TestCase):
    """Caminhos sem form (ORM, shell, /admin/): quem barra é o banco."""

    def test_indice_existe(self):
        self.assertIn(INDICE, indices_categorias())

    def test_mesmo_nome_com_caixa_e_espacos_nas_pontas_colide(self):
        Categoria.objects.create(nome="Bonés")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Categoria.objects.create(nome=" bonés ")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Categoria.objects.create(nome="BONéS")  # só A-Z muda de caixa: vale também no SQLite
        self.assertEqual(list(Categoria.objects.values_list("nome", flat=True)), ["Bonés"])

    @unittest.skipIf(connection.vendor == "mysql",
                     "MySQL: o collation (utf8mb4_*_ci) ignora acentos, então o unique da coluna "
                     "já faz 'Calças' e 'Calcas' colidirem")
    def test_acento_e_espaco_interno_contam_sqlite_postgresql(self):
        # SQLite e PostgreSQL: LOWER(TRIM()) não remove acentos nem espaços internos
        Categoria.objects.create(nome="Calças")
        Categoria.objects.create(nome="Calcas")
        Categoria.objects.create(nome="Cal ças")
        self.assertEqual(Categoria.objects.count(), 3)


class MigracaoCategoriaUnicaTest(TransactionTestCase):
    """A 0006 não corrige dados: com categorias que colidem ela aborta e não cria o índice."""

    antes = [("loja", "0005_email_unico")]
    depois = [("loja", "0006_categoria_nome_unico_ci")]

    def migrar(self, alvo):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(alvo)

    def tearDown(self):
        # remove a colisão (senão a própria 0006 barra a volta) e restaura o leaf com o índice
        Categoria.objects.all().delete()
        self.migrar(MigrationExecutor(connection).loader.graph.leaf_nodes())
        self.assertIn(INDICE, indices_categorias())

    def test_colisao_bloqueia_migration_sem_alterar_dados(self):
        self.migrar(self.antes)
        self.assertNotIn(INDICE, indices_categorias())
        # pares aceitos pelo unique da coluna em qualquer banco (no MySQL, espaço no início conta)
        a = Categoria.objects.create(nome="Moletons")
        b = Categoria.objects.create(nome="  moletons")
        c = Categoria.objects.create(nome="Calças")
        antes = sorted(Categoria.objects.values_list("id", "nome"))

        with self.assertRaisesMessage(Exception, "1 grupo(s) de categorias") as ctx:
            self.migrar(self.depois)
        msg = str(ctx.exception)
        self.assertIn(f"id {a.id} “Moletons”", msg)
        self.assertIn(f"id {b.id} “  moletons”", msg)
        self.assertNotIn(f"id {c.id}", msg)
        self.assertIn("Resolva manualmente", msg)

        self.assertNotIn(INDICE, indices_categorias())
        aplicadas = MigrationExecutor(connection).loader.applied_migrations
        self.assertNotIn(self.depois[0], aplicadas)
        self.assertIn(self.antes[0], aplicadas)
        self.assertEqual(sorted(Categoria.objects.values_list("id", "nome")), antes)  # nada mudou

    def test_sem_colisao_cria_indice_e_reverse_remove(self):
        self.migrar(self.antes)
        Categoria.objects.create(nome="Moletons")
        self.migrar(self.depois)
        self.assertIn(INDICE, indices_categorias())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Categoria.objects.create(nome=" MOLETONS")
        self.migrar(self.antes)
        self.assertNotIn(INDICE, indices_categorias())


def _passa_validacao(self):  # simula a corrida: a validação do form não viu a outra categoria
    return self.cleaned_data["nome"]


@mock.patch.object(CategoriaForm, "validate_unique", lambda self: None)
@mock.patch.object(CategoriaForm, "clean_nome", _passa_validacao)
class CorridaPainelCategoriaTest(TestCase):
    """Duas pessoas salvam ao mesmo tempo: o form passa nas duas, o índice do banco decide."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("equipe_cat", password="x", is_staff=True)
        cls.moletons = Categoria.objects.create(nome="Moletons")
        cls.bones = Categoria.objects.create(nome="Bonés")

    def setUp(self):
        self.client.force_login(self.staff)

    def mensagens(self, resposta):
        return [str(m) for m in get_messages(resposta.wsgi_request)]

    def test_criar_com_outra_caixa(self):
        antes = sorted(Categoria.objects.values_list("id", "nome"))
        r = self.client.post(reverse("loja:painel_categoria_nova"), {"nome": "MOLETONS"})
        self.assertRedirects(r, reverse("loja:painel_categorias"))
        self.assertEqual(self.mensagens(r), [f"Categoria não salva: {CATEGORIA_REPETIDA}"])
        self.assertEqual(sorted(Categoria.objects.values_list("id", "nome")), antes)

    def test_renomear_para_nome_de_outra_em_outra_caixa(self):
        antes = sorted(Categoria.objects.values_list("id", "nome"))
        r = self.client.post(reverse("loja:painel_categoria_editar", args=[self.bones.id]),
                             {"nome": "moletons"})
        self.assertRedirects(r, reverse("loja:painel_categorias"))
        self.assertEqual(self.mensagens(r), [f"Categoria não salva: {CATEGORIA_REPETIDA}"])
        self.assertEqual(sorted(Categoria.objects.values_list("id", "nome")), antes)


class MidiaIsoladaTest(TestCase):
    """O runner (config.test_runner) troca MEDIA_ROOT por um temporário durante a suíte."""

    def test_media_root_e_temporario(self):
        media = Path(settings.MEDIA_ROOT).resolve()
        self.assertNotEqual(media, (Path(settings.BASE_DIR) / "media").resolve())
        self.assertEqual(media.parent, Path(tempfile.gettempdir()).resolve())
