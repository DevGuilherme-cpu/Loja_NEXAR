from django.db import migrations


# tênis com modelo próprio, separado em partes para o personalizador
def trocar(apps, schema_editor):
    Produto = apps.get_model("loja", "Produto")
    Produto.objects.filter(modelo_3d="/static/modelos/tenis.glb").update(modelo_3d="/static/modelos/tenis-nexar.glb")


def voltar(apps, schema_editor):
    Produto = apps.get_model("loja", "Produto")
    Produto.objects.filter(modelo_3d="/static/modelos/tenis-nexar.glb").update(modelo_3d="/static/modelos/tenis.glb")


class Migration(migrations.Migration):
    dependencies = [("loja", "0003_cores_e_modelos_locais")]
    operations = [migrations.RunPython(trocar, voltar)]
