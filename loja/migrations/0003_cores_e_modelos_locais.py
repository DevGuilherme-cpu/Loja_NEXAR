from django.db import migrations

# Cor real de cada peça (vira a cor do 3D) e os .glb servidos pelo próprio site
CORES = {
    "Camiseta Box Logo": "#E8641E",
    "Camiseta Grid": "#F2F2EF",
    "Moletom Heavy": "#22306B",
    "Moletom Drop 01": "#EDEDE9",
    "Calça Cargo Tech": "#5B6542",
    "Calça Wide Denim": "#8FB3D9",
    "Boné 6-Panel": "#F4F4F1",
}
MODELOS = {"Khronos": None, "MaterialsVariantsShoe": "/static/modelos/tenis.glb",
           "SunglassesKhronos": "/static/modelos/oculos.glb"}


def preencher(apps, schema_editor):
    Produto = apps.get_model("loja", "Produto")
    for nome, cor in CORES.items():
        Produto.objects.filter(nome=nome, cor="").update(cor=cor)
    # troca os links do GitHub (lentos e dependem de internet) pelos arquivos em static/modelos
    for p in Produto.objects.filter(modelo_3d__contains="raw.githubusercontent.com"):
        for trecho, local in MODELOS.items():
            if local and trecho in p.modelo_3d.name:
                Produto.objects.filter(pk=p.pk).update(modelo_3d=local)


class Migration(migrations.Migration):
    dependencies = [("loja", "0002_produto_cor")]
    operations = [migrations.RunPython(preencher, migrations.RunPython.noop)]
