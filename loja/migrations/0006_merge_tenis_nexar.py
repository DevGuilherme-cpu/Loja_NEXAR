"""Migration de merge (não altera tabelas).

A 0004_tenis_nexar (PR #8, troca do modelo 3D do tênis) e a 0004_pedido_preco_unitario
(este PR) partem da 0003. Esta migration junta os dois caminhos para o Django ter uma única
"ponta"; sem ela o migrate falha com "Conflicting migrations detected".
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("loja", "0005_email_unico"),
        ("loja", "0004_tenis_nexar"),
    ]
    operations = []
