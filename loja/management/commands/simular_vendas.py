"""python manage.py simular_vendas [quantidade] [--dias N]: cria pedidos fictícios para a demonstração."""
from django.core.management.base import BaseCommand

from loja.simulacao import simular_pedidos


class Command(BaseCommand):
    help = "Cria pedidos fictícios (com baixa de estoque) espalhados pelos últimos dias."

    def add_arguments(self, parser):
        parser.add_argument("quantidade", type=int, nargs="?", default=20)
        parser.add_argument("--dias", type=int, default=30)

    def handle(self, *args, quantidade, dias, **opcoes):
        criados = simular_pedidos(max(quantidade, 1), max(dias, 1))
        self.stdout.write(self.style.SUCCESS(f"{len(criados)} pedidos fictícios criados."))
