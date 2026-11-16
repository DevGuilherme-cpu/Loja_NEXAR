from .models import Categoria


# Categorias no menu/rodapé de todas as páginas
def categorias(request):
    return {"categorias": Categoria.objects.all()}
