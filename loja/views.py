from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

# shortcut: dados falsos até o Eliton criar os models; ele troca por Produto.objects...
from .mock_data import CATEGORIAS, PEDIDOS, PRODUTOS


def index(request):
    return render(request, "index.html", {"destaques": PRODUTOS[:4]})


def produtos(request):
    busca = request.GET.get("busca", "").strip()
    categoria = request.GET.get("categoria", "")
    lista = [p for p in PRODUTOS
             if busca.lower() in p["nome"].lower()
             and (not categoria or str(p["categoria_id"]) == categoria)]
    return render(request, "produtos.html", {"produtos": lista, "busca": busca, "categoria": categoria})


def produto(request, id):
    p = next((p for p in PRODUTOS if p["id"] == id), None)
    if p is None:
        raise Http404("Produto não encontrado")
    return render(request, "produto.html", {"produto": p})


def entrar(request):
    return render(request, "login.html")


def cadastro(request):
    return render(request, "cadastro.html")


# ---------- painel admin ----------
# shortcut: as telas só exibem dados falsos e as ações (salvar/excluir) não gravam nada.
# Eliton: troque pelo CRUD de verdade (INSERT/UPDATE/DELETE) e proteja com @staff_member_required.

def painel_produtos(request):
    busca = request.GET.get("busca", "").strip()
    lista = [p for p in PRODUTOS if busca.lower() in p["nome"].lower()]
    return render(request, "painel/produtos.html", {"produtos": lista, "busca": busca})


def painel_produto_form(request, id=None):
    produto = None
    if id is not None:
        produto = next((p for p in PRODUTOS if p["id"] == id), None)
        if produto is None:
            raise Http404("Produto não encontrado")
    if request.method == "POST":
        messages.info(request, "Salvar simulado: ainda não grava no banco.")
        return redirect("loja:painel_produtos")
    return render(request, "painel/produto_form.html", {"produto": produto})


@require_POST
def painel_produto_excluir(request, id):
    messages.error(request, "Exclusão simulada: ainda não apaga do banco.")
    return redirect("loja:painel_produtos")


def painel_categorias(request):
    lista = [{**c, "total": sum(p["categoria_id"] == c["id"] for p in PRODUTOS)} for c in CATEGORIAS]
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
    return render(request, "painel/pedidos.html", {"pedidos": PEDIDOS})