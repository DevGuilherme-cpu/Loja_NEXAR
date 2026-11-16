# shortcut: lista falsa; Eliton troca por Categoria.objects.all()
from .mock_data import CATEGORIAS


def categorias(request):
    return {"categorias": CATEGORIAS}