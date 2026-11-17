"""E-mail único sem diferenciar maiúsculas/minúsculas (contas com e-mail preenchido).

Cria um índice único funcional em auth_user sobre NULLIF(LOWER(email), ''):
- e-mails que diferem só na caixa colidem;
- e-mail vazio vira NULL no índice, e NULLs não conflitam (SQLite, PostgreSQL, MySQL 8.0.13+),
  então contas sem e-mail (demonstrativas, createsuperuser) continuam permitidas.

Antes de criar o índice há uma verificação SOMENTE LEITURA: se já existirem e-mails repetidos,
a migration para com uma mensagem listando-os (mascarados). Nenhuma conta é apagada,
juntada ou alterada; a correção é manual.

Protege também caminhos que não passam pelos forms: createsuperuser, shell/ORM, scripts.
"""
from django.db import migrations
from django.db.models import Count
from django.db.models.functions import Lower

INDICE = "auth_user_email_ci_uniq"


class EmailsDuplicados(Exception):
    pass


def mascarar(email):
    local, _, dominio = email.partition("@")
    return f"{local[:1]}***@{dominio}" if dominio else f"{email[:1]}***"


def verificar_duplicados(apps, schema_editor):
    User = apps.get_model("auth", "User")
    repetidos = list(
        User.objects.using(schema_editor.connection.alias)
        .exclude(email="")
        .annotate(email_ci=Lower("email"))
        .values("email_ci")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .order_by("email_ci")
    )
    if repetidos:
        contas = sum(r["total"] for r in repetidos)
        lista = ", ".join(f"{mascarar(r['email_ci'])} ({r['total']} contas)" for r in repetidos)
        raise EmailsDuplicados(
            f"Não foi possível criar o índice único de e-mail: {len(repetidos)} e-mail(s) repetido(s) "
            f"(ignorando maiúsculas/minúsculas) em {contas} contas: {lista}. "
            "Resolva manualmente (altere ou remova o e-mail das contas extras no /admin/) "
            "e rode o migrate de novo. Nenhuma conta foi alterada."
        )


def _tabela(apps, schema_editor):
    return schema_editor.quote_name(apps.get_model("auth", "User")._meta.db_table)


def criar_indice(apps, schema_editor):
    verificar_duplicados(apps, schema_editor)
    # Parênteses duplos: exigência do MySQL para índice funcional (aceito também por SQLite/PostgreSQL)
    schema_editor.execute(
        f"CREATE UNIQUE INDEX {schema_editor.quote_name(INDICE)} "
        f"ON {_tabela(apps, schema_editor)} ((NULLIF(LOWER(email), '')))"
    )


def remover_indice(apps, schema_editor):
    nome = schema_editor.quote_name(INDICE)
    if schema_editor.connection.vendor == "mysql":
        schema_editor.execute(f"DROP INDEX {nome} ON {_tabela(apps, schema_editor)}")
    else:
        schema_editor.execute(f"DROP INDEX {nome}")


class Migration(migrations.Migration):

    dependencies = [
        ("loja", "0004_pedido_preco_unitario"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(criar_indice, remover_indice),
    ]
