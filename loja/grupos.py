"""Grupos de usuários no banco (tabelas auth_group e auth_user_groups do Django).

Clientes = quem compra na loja. Funcionários = a equipe (is_staff), que entra no painel.
Todo usuário salvo fica no grupo certo: cadastro na loja, criação pelo admin, simulação de vendas
e quando alguém vira (ou deixa de ser) funcionário.
"""
from django.contrib.auth.models import Group

CLIENTES = "Clientes"
FUNCIONARIOS = "Funcionários"


def acertar_grupo(sender, instance, update_fields=None, raw=False, **kwargs):
    # login só grava o last_login: não precisa mexer nos grupos (evita 2 consultas a cada entrada)
    if raw or (update_fields and set(update_fields) <= {"last_login"}):
        return
    certo, errado = (FUNCIONARIOS, CLIENTES) if instance.is_staff else (CLIENTES, FUNCIONARIOS)
    instance.groups.add(Group.objects.get_or_create(name=certo)[0])
    instance.groups.remove(*Group.objects.filter(name=errado))
