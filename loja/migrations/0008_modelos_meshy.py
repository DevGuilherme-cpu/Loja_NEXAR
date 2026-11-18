from django.db import migrations

# modelos 3D próprios (Meshy + ferramentas/otimizar_glb.py), em branco: o site tinge com Produto.cor
MODELOS = {
    "Camisetas": "/static/modelos/camiseta.glb",
    "Moletons": "/static/modelos/moletom.glb",
    "Calças": "/static/modelos/calca.glb",
    "Bonés": "/static/modelos/bone.glb",
}


def ligar(apps, schema_editor):
    Produto = apps.get_model("loja", "Produto")
    for categoria, arquivo in MODELOS.items():
        # só quem ainda usa a peça gerada; produto com modelo próprio não muda
        Produto.objects.filter(categoria__nome=categoria, modelo_3d="").update(modelo_3d=arquivo)


def desligar(apps, schema_editor):
    Produto = apps.get_model("loja", "Produto")
    Produto.objects.filter(modelo_3d__in=MODELOS.values()).update(modelo_3d="")


class Migration(migrations.Migration):
    dependencies = [("loja", "0007_merge_categoria_tenis")]
    operations = [migrations.RunPython(ligar, desligar)]
