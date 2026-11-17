from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Categoria, Pedido, Produto

# produtos já com a categoria (JOIN)
PRODUTOS = Produto.objects.select_related("categoria")


def filtrar(busca, categoria=""):
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


# Painel
# TODO: gravar no banco (salvar/excluir ainda são simulados)

@staff_member_required
def painel_produtos(request):
    busca = request.GET.get("busca", "").strip()
    return render(request, "painel/produtos.html", {"produtos": filtrar(busca), "busca": busca})


@staff_member_required
def painel_produto_form(request, id=None):
    produto = get_object_or_404(PRODUTOS, id=id) if id is not None else None
    if request.method == "POST":
        messages.info(request, "Salvar simulado: ainda não grava no banco.")
        return redirect("loja:painel_produtos")
    return render(request, "painel/produto_form.html", {"produto": produto})


@staff_member_required
@require_POST
def painel_produto_excluir(request, id):
    messages.error(request, "Exclusão simulada: ainda não apaga do banco.")
    return redirect("loja:painel_produtos")


@staff_member_required
def painel_categorias(request):
    lista = Categoria.objects.annotate(total=Count("produto"))
    return render(request, "painel/categorias.html", {"lista": lista})


@staff_member_required
@require_POST
def painel_categoria_salvar(request, id=None):  # sem id = nova
    messages.info(request, "Salvar simulado: ainda não grava no banco.")
    return redirect("loja:painel_categorias")


@staff_member_required
@require_POST
def painel_categoria_excluir(request, id):
    messages.error(request, "Exclusão simulada: ainda não apaga do banco.")
    return redirect("loja:painel_categorias")


@staff_member_required
def painel_pedidos(request):
    # JOIN pedidos + usuário + produto + categoria
    pedidos = Pedido.objects.select_related("usuario", "produto__categoria")
    return render(request, "painel/pedidos.html", {"pedidos": pedidos})