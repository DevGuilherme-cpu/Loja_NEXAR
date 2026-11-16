from django.urls import path

from . import views

app_name = "loja"

urlpatterns = [
    path("", views.index, name="index"),
    path("produtos/", views.produtos, name="produtos"),
    path("produto/<int:id>/", views.produto, name="produto"),
    path("entrar/", views.entrar, name="entrar"),
    path("cadastro/", views.cadastro, name="cadastro"),

    # painel admin
    path("painel/", views.painel_produtos, name="painel_produtos"),
    path("painel/produtos/novo/", views.painel_produto_form, name="painel_produto_novo"),
    path("painel/produtos/<int:id>/editar/", views.painel_produto_form, name="painel_produto_editar"),
    path("painel/produtos/<int:id>/excluir/", views.painel_produto_excluir, name="painel_produto_excluir"),
    path("painel/categorias/", views.painel_categorias, name="painel_categorias"),
    path("painel/categorias/nova/", views.painel_categoria_salvar, name="painel_categoria_nova"),
    path("painel/categorias/<int:id>/editar/", views.painel_categoria_salvar, name="painel_categoria_editar"),
    path("painel/categorias/<int:id>/excluir/", views.painel_categoria_excluir, name="painel_categoria_excluir"),
    path("painel/pedidos/", views.painel_pedidos, name="painel_pedidos"),
]