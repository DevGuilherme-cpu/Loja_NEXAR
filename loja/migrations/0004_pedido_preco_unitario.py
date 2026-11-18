"""Grava o preço da compra no pedido (preco_unitario) e adiciona CHECKs.

Feita em etapas para funcionar em banco que já tem pedidos (SQLite, MySQL e PostgreSQL):
1. verifica (somente leitura) se há dados que violariam as CHECKs e, se houver, aborta;
2. cria a coluna aceitando NULL;
3. preenche cada pedido existente com o preço ATUAL do produto;
4. torna a coluna NOT NULL;
5. adiciona as constraints.

Sobre o passo 1: a migração NÃO corrige dados sozinha. Se existir produto com preço negativo
ou pedido com quantidade menor que 1, ela para com uma mensagem listando os ids (até 20).
A verificação vem ANTES de qualquer alteração de estrutura de propósito: no MySQL o DDL não é
transacional, e assim nada fica aplicado pela metade. Em PostgreSQL e SQLite a migração
inteira roda numa transação de qualquer forma.
Como preco_unitario é copiado de produto.preco, verificar preco >= 0 já garante
preco_unitario >= 0 nos pedidos existentes.

Sobre o passo 3: antes desta migração o banco NÃO guardava o preço pago em cada pedido,
então não existe histórico para recuperar. O preço atual do produto é a melhor informação
disponível; se um produto já foi reajustado, o pedido antigo fica com o preço novo.
Corrija manualmente os pedidos em que isso importar.
"""
import django.core.validators
from django.db import migrations, models

LIMITE_IDS = 20


def _ids(queryset):
    ids = list(queryset.order_by("pk").values_list("pk", flat=True)[:LIMITE_IDS + 1])
    texto = ", ".join(str(i) for i in ids[:LIMITE_IDS])
    return texto + (" ..." if len(ids) > LIMITE_IDS else "")


def verificar_dados_para_constraints(apps, schema_editor):
    """Somente leitura: aborta a migração se houver dados que violam as novas CHECKs."""
    Produto = apps.get_model("loja", "Produto")
    Pedido = apps.get_model("loja", "Pedido")
    db = schema_editor.connection.alias

    problemas = []
    precos = Produto.objects.using(db).filter(preco__lt=0)
    if (n := precos.count()):
        problemas.append(f"- {n} produto(s) com preço negativo (preco < 0). ids: {_ids(precos)}")
    quantidades = Pedido.objects.using(db).filter(quantidade__lt=1)
    if (n := quantidades.count()):
        problemas.append(f"- {n} pedido(s) com quantidade menor que 1. ids: {_ids(quantidades)}")

    if problemas:
        raise RuntimeError(
            "Migração loja.0004 interrompida: há dados que violam as novas regras do banco.\n"
            + "\n".join(problemas)
            + "\nCorrija esses registros manualmente (no /admin/ ou por SQL) e rode o migrate de novo. "
            "Nenhum dado foi corrigido automaticamente."
        )


def preencher_preco_unitario(apps, schema_editor):
    Pedido = apps.get_model("loja", "Pedido")
    db = schema_editor.connection.alias
    for pedido in Pedido.objects.using(db).filter(preco_unitario__isnull=True).select_related("produto"):
        pedido.preco_unitario = pedido.produto.preco
        pedido.save(update_fields=["preco_unitario"])


class Migration(migrations.Migration):

    dependencies = [
        ("loja", "0003_cores_e_modelos_locais"),
    ]

    operations = [
        migrations.RunPython(verificar_dados_para_constraints, migrations.RunPython.noop),
        migrations.AddField(
            model_name="pedido",
            name="preco_unitario",
            field=models.DecimalField(decimal_places=2, max_digits=10, null=True),
        ),
        migrations.RunPython(preencher_preco_unitario, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="pedido",
            name="preco_unitario",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10,
                                      validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name="pedido",
            name="quantidade",
            field=models.PositiveIntegerField(default=1,
                                              validators=[django.core.validators.MinValueValidator(1)]),
        ),
        migrations.AlterField(
            model_name="produto",
            name="preco",
            field=models.DecimalField(decimal_places=2, max_digits=10,
                                      validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AddConstraint(
            model_name="produto",
            constraint=models.CheckConstraint(condition=models.Q(preco__gte=0), name="produto_preco_nao_negativo"),
        ),
        migrations.AddConstraint(
            model_name="pedido",
            constraint=models.CheckConstraint(condition=models.Q(quantidade__gte=1), name="pedido_quantidade_minima_1"),
        ),
        migrations.AddConstraint(
            model_name="pedido",
            constraint=models.CheckConstraint(condition=models.Q(preco_unitario__gte=0),
                                              name="pedido_preco_unitario_nao_negativo"),
        ),
    ]
