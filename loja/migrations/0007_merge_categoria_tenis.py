"""Migration de merge (não altera tabelas): junta a 0006_categoria_nome_unico_ci (este PR)
com a 0006_merge_tenis_nexar (PR #5 + PR #8), deixando uma única "ponta" no Django."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("loja", "0006_categoria_nome_unico_ci"),
        ("loja", "0006_merge_tenis_nexar"),
    ]
    operations = []
