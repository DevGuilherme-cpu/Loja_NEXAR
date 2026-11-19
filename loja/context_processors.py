from .models import Categoria


# categorias do menu
def categorias(request):
    return {"categorias": Categoria.objects.all()}


# número de peças no ícone da sacola (lido da sessão, sem consultar o banco)
def sacola(request):
    return {"sacola_pecas": sum(linha["quantidade"] for linha in request.session.get("sacola", []))}
