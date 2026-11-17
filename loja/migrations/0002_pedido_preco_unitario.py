"""Grava o preço da compra no pedido (preco_unitario) e adiciona CHECKs.

Feita em etapas para funcionar em banco que já tem pedidos (SQLite, MySQL e PostgreSQL):
1. cria a coluna aceitando NULL;
2. preenche cada pedido com o preço atual do produto (melhor informação disponível);
3. torna a coluna NOT NULL;
4. adiciona as constraints.
"""
import django.core.validators
from django.db import migrations, models


def preencher_preco_unitario(apps, schema_editor):
    Pedido = apps.get_model("loja", "Pedido")
    db = schema_editor.connection.alias
    for pedido in Pedido.objects.using(db).filter(preco_unitario__isnull=True).select_related("produto"):
        pedido.preco_unitario = pedido.produto.preco
        pedido.save(update_fields=["preco_unitario"])


class Migration(migrations.Migration):

    dependencies = [
        ("loja", "0001_initial"),
    ]

    operations = [
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
