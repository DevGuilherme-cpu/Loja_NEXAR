import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def copiar_para_itens(apps, schema_editor):
    """Cada pedido antigo (uma peça só) vira um pedido com 1 item, com o mesmo preço pago."""
    Pedido = apps.get_model("loja", "Pedido")
    ItemPedido = apps.get_model("loja", "ItemPedido")
    ItemPedido.objects.bulk_create(
        [ItemPedido(pedido_id=p.id, produto_id=p.produto_id, tamanho=p.tamanho, quantidade=p.quantidade,
                    preco_unitario=p.preco_unitario) for p in Pedido.objects.all()],
        batch_size=500,
    )


class Migration(migrations.Migration):
    """Sacola: um pedido passa a ter vários itens. Os campos antigos saem na 0013, numa migration
    separada (no PostgreSQL, copiar os dados e apagar colunas na mesma transação dá erro)."""

    dependencies = [
        ("loja", "0011_compra_sem_conta"),
    ]

    operations = [
        migrations.CreateModel(
            name="ItemPedido",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tamanho", models.CharField(choices=[("P", "P"), ("M", "M"), ("G", "G"), ("GG", "GG"), ("38", "38"),
                                                      ("39", "39"), ("40", "40"), ("41", "41"), ("42", "42"),
                                                      ("43", "43"), ("44", "44"), ("U", "Único")], max_length=2)),
                ("quantidade", models.PositiveIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)])),
                ("preco_unitario", models.DecimalField(blank=True, decimal_places=2, max_digits=10,
                                                       validators=[django.core.validators.MinValueValidator(0)])),
                ("pedido", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="itens",
                                             to="loja.pedido")),
                ("produto", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="loja.produto")),
            ],
            options={
                "verbose_name": "item do pedido",
                "verbose_name_plural": "itens do pedido",
                "db_table": "itens_pedido",
                "ordering": ["id"],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("quantidade__gte", 1)), name="item_quantidade_minima_1"),
                    models.CheckConstraint(condition=models.Q(("preco_unitario__gte", 0)),
                                           name="item_preco_unitario_nao_negativo"),
                ],
            },
        ),
        # volta (migrate loja 0011): os campos antigos do pedido ainda estão lá, nada a desfazer
        migrations.RunPython(copiar_para_itens, migrations.RunPython.noop),
    ]
