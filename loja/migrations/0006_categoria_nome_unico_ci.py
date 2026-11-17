"""Nome de categoria único sem diferenciar maiúsculas/minúsculas, garantido no banco.

Regra: duas categorias colidem quando LOWER(TRIM(nome)) é igual.
- espaços nas pontas não contam ("Bonés" = " bonés ");
- espaços internos e acentos contam ("Calças" ≠ "Calcas", "Calça s" ≠ "Calças").

Cria o índice único funcional categorias_nome_ci_uniq sobre (LOWER(TRIM(nome))). Ele protege
também o que não passa pelo CategoriaForm: /admin/, shell/ORM, scripts e a corrida entre dois
POSTs simultâneos no painel (a view trata o IntegrityError com CATEGORIA_REPETIDA).

Diferenças por banco (o unique=True de Categoria.nome continua existindo):
- PostgreSQL: o unique da coluna diferencia caixa; quem barra "Bonés"/"BONÉS" é este índice.
  LOWER segue o locale do banco (UTF-8: converte também letras acentuadas).
- SQLite (testes): LOWER só converte A-Z; "Bonés"/"BONÉS" (É maiúsculo) não colidem no índice.
  O CategoriaForm (nome__iexact) continua barrando no painel.
- MySQL (utf8mb4_unicode_ci / utf8mb4_0900_ai_ci): o collation já compara sem caixa E sem acento,
  então o próprio unique da coluna faz "Calças" e "Calcas" colidirem (no PostgreSQL não colidem).
  O índice aqui acrescenta o TRIM (espaços no início não são ignorados pelo collation).

Antes do índice há uma verificação SOMENTE LEITURA: se já houver categorias que colidem, a
migration para listando ids e nomes. Nada é renomeado, juntado ou apagado; a correção é manual.
"""
from collections import defaultdict

from django.db import migrations
from django.db.models.functions import Lower, Trim

INDICE = "categorias_nome_ci_uniq"


class CategoriasDuplicadas(Exception):
    pass


def verificar_duplicados(apps, schema_editor):
    Categoria = apps.get_model("loja", "Categoria")
    grupos = defaultdict(list)
    linhas = (
        Categoria.objects.using(schema_editor.connection.alias)
        .annotate(chave=Lower(Trim("nome")))  # a chave é calculada pelo próprio banco, como no índice
        .values_list("chave", "id", "nome")
        .order_by("id")
    )
    for chave, id_, nome in linhas:
        grupos[chave].append((id_, nome))
    repetidos = [g for g in grupos.values() if len(g) > 1]
    if repetidos:
        lista = "; ".join(", ".join(f"id {i} “{n}”" for i, n in g) for g in repetidos)
        raise CategoriasDuplicadas(
            f"Não foi possível criar o índice único de categoria: {len(repetidos)} grupo(s) de "
            f"categorias com o mesmo nome (ignorando maiúsculas/minúsculas e espaços nas pontas): "
            f"{lista}. Resolva manualmente (renomeie, ou mova os produtos e exclua a categoria extra "
            "no /admin/) e rode o migrate de novo. Nenhuma categoria foi alterada."
        )


def _tabela(apps, schema_editor):
    return schema_editor.quote_name(apps.get_model("loja", "Categoria")._meta.db_table)


def criar_indice(apps, schema_editor):
    # Parênteses duplos: exigência do MySQL para índice funcional (aceito também por SQLite/PostgreSQL)
    schema_editor.execute(
        f"CREATE UNIQUE INDEX {schema_editor.quote_name(INDICE)} "
        f"ON {_tabela(apps, schema_editor)} ((LOWER(TRIM(nome))))"
    )


def remover_indice(apps, schema_editor):
    nome = schema_editor.quote_name(INDICE)
    if schema_editor.connection.vendor == "mysql":
        schema_editor.execute(f"DROP INDEX {nome} ON {_tabela(apps, schema_editor)}")
    else:
        schema_editor.execute(f"DROP INDEX {nome}")


class Migration(migrations.Migration):

    dependencies = [
        ("loja", "0005_email_unico"),
    ]

    operations = [
        # 1) verificação somente leitura (aborta antes de qualquer DDL se houver colisão)
        migrations.RunPython(verificar_duplicados, migrations.RunPython.noop),
        # 2) o índice. atomic=False: no MySQL o DDL não é transacional e o Django recusa
        #    executar DDL dentro de transaction.atomic. No PostgreSQL/SQLite a migration
        #    inteira continua numa transação.
        migrations.RunPython(criar_indice, remover_indice, atomic=False),
    ]
