from django.db import migrations


class Migration(migrations.Migration):
    """Produto, tamanho, quantidade e preço já foram copiados para itens_pedido (0012)."""

    dependencies = [
        ("loja", "0012_itens_do_pedido"),
    ]

    operations = [
        migrations.RemoveConstraint(model_name="pedido", name="pedido_quantidade_minima_1"),
        migrations.RemoveConstraint(model_name="pedido", name="pedido_preco_unitario_nao_negativo"),
        migrations.RemoveField(model_name="pedido", name="produto"),
        migrations.RemoveField(model_name="pedido", name="tamanho"),
        migrations.RemoveField(model_name="pedido", name="quantidade"),
        migrations.RemoveField(model_name="pedido", name="preco_unitario"),
    ]
