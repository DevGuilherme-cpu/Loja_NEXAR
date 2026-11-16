from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Categoria, Pedido, Produto

# select_related("categoria") = JOIN com categorias numa consulta só (o card mostra o nome da categoria)
PRODUTOS = Produto.objects.select_related("categoria")


def filtrar(busca, categoria=""):
    # SELECT ... WHERE nome LIKE '%busca%' [AND categoria_id = ...]
    lista = PRODUTOS.filter(nome__icontains=busca)
    return lista.filter(categoria_id=categoria) if categoria.isdigit() else lista


def index(request):
    return render(request, "index.html", {"destaques": PRODUTOS[:4]})


def produtos(request):
    busca = request.GET.get("busca", "").strip()
    categoria = request.GET.get("categoria", "")
    return render(request, "produtos.html",
                  {"produtos": filtrar(busca, categoria), "busca": busca, "categoria": categoria})


def produto(request, id):
    return render(request, "produto.html", {"produto": get_object_or_404(PRODUTOS, id=id)})


def entrar(request):
    return render(request, "login.html")


def cadastro(request):
    return render(request, "cadastro.html")


# ---------- painel admin ----------
# A LEITURA já vem do banco. shortcut: salvar/excluir ainda não gravam nada.
# Eliton: fazer o CRUD de verdade (INSERT/UPDATE/DELETE) e proteger com @staff_member_required.

def painel_produtos(request):
    busca = request.GET.get("busca", "").strip()
    return render(request, "painel/produtos.html", {"produtos": filtrar(busca), "busca": busca})


def painel_produto_form(request, id=None):
    produto = get_object_or_404(PRODUTOS, id=id) if id is not None else None
    if request.method == "POST":
        messages.info(request, "Salvar simulado: ainda não grava no banco.")
        return redirect("loja:painel_produtos")
    return render(request, "painel/produto_form.html", {"produto": produto})


@require_POST
def painel_produto_excluir(request, id):
    messages.error(request, "Exclusão simulada: ainda não apaga do banco.")
    return redirect("loja:painel_produtos")


def painel_categorias(request):
    # SELECT categorias.*, COUNT(produtos.id) ... LEFT JOIN produtos ... GROUP BY categorias.id
    lista = Categoria.objects.annotate(total=Count("produto"))
    return render(request, "painel/categorias.html", {"lista": lista})


@require_POST
def painel_categoria_salvar(request, id=None):  # sem id = nova, com id = editar
    messages.info(request, "Salvar simulado: ainda não grava no banco.")
    return redirect("loja:painel_categorias")


@require_POST
def painel_categoria_excluir(request, id):
    messages.error(request, "Exclusão simulada: ainda não apaga do banco.")
    return redirect("loja:painel_categorias")


def painel_pedidos(request):
    # O JOIN do trabalho: pedidos + auth_user + produtos + categorias numa consulta só
    pedidos = Pedido.objects.select_related("usuario", "produto__categoria")
    return render(request, "painel/pedidos.html", {"pedidos": pedidos})