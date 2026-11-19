"""Vendas fictícias para demonstração: cria pedidos de verdade no banco (com baixa de estoque),
de clientes de exemplo, espalhados pelos últimos dias. Usado pelo botão do painel e por
python manage.py simular_vendas."""
import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Pedido, Produto

CLIENTES = ["marina.alves", "joao.pedro", "lucas.ferreira", "beatriz.lima", "rafael.costa", "julia.martins",
            "gabriel.rocha", "larissa.nunes", "thiago.ramos", "camila.duarte", "pedro.henrique", "sofia.mendes"]


def cliente_ficticio(nome):
    usuario, criado = User.objects.get_or_create(username=nome)
    if criado:
        usuario.set_unusable_password()  # conta de exemplo: ninguém entra com ela
        usuario.save(update_fields=["password"])
    return usuario


@transaction.atomic
def simular_pedidos(quantidade=6, dias=14):
    """Cria até `quantidade` pedidos. O primeiro é de agora (aparece no topo); os outros, nos últimos `dias`."""
    agora = timezone.now()
    criados = []
    for i in range(quantidade):
        produto = Produto.objects.filter(estoque__gt=0).order_by("?").first()
        if produto is None:
            break  # tudo esgotado
        qtd = 1 if produto.estoque < 2 else random.choice([1, 1, 1, 2])
        # mesma regra da compra pela loja: o UPDATE só baixa se ainda houver estoque
        if not Produto.objects.filter(id=produto.id, estoque__gte=qtd).update(estoque=F("estoque") - qtd):
            continue
        pedido = Pedido.com_item(produto, random.choice(produto.tamanhos), qtd, produto.preco,
                                 usuario=cliente_ficticio(random.choice(CLIENTES)))
        if i:
            data = agora - timedelta(days=random.randint(0, dias - 1), hours=random.randint(0, 23),
                                     minutes=random.randint(0, 59))
            Pedido.objects.filter(pk=pedido.pk).update(data=data)
        criados.append(pedido)
    return criados
