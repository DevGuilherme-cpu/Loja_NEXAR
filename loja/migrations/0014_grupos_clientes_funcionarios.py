from django.db import migrations


def criar_grupos(apps, schema_editor):
    """Cria os grupos e coloca cada usuário que já existe no seu: equipe (is_staff) ou cliente."""
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("auth", "User")
    clientes, _ = Group.objects.get_or_create(name="Clientes")
    funcionarios, _ = Group.objects.get_or_create(name="Funcionários")
    for usuario in User.objects.all():
        usuario.groups.add(funcionarios if usuario.is_staff else clientes)


def apagar_grupos(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name__in=["Clientes", "Funcionários"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("loja", "0013_pedido_sem_campos_do_item"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(criar_grupos, apagar_grupos)]
