from .models import Categoria


# categorias do menu
def categorias(request):
    return {"categorias": Categoria.objects.all()}
