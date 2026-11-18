from django.urls import path

from . import views

app_name = "loja"

urlpatterns = [
    path("", views.index, name="index"),
    path("produtos/", views.produtos, name="produtos"),
    path("produto/<int:id>/", views.produto, name="produto"),
    path("pedido/", views.pedido, name="pedido"),
    path("entrar/", views.Entrar.as_view(), name="entrar"),
    path("cadastro/", views.cadastro, name="cadastro"),
    path("sair/", views.Sair.as_view(), name="sair"),

    # painel admin
    path("painel/", views.painel_inicio, name="painel_inicio"),
    path("painel/assistente/", views.painel_assistente, name="painel_assistente"),
    path("painel/simular/", views.painel_simular, name="painel_simular"),
    path("painel/produtos/", views.painel_produtos, name="painel_produtos"),
    path("painel/produtos/novo/", views.painel_produto_form, name="painel_produto_novo"),
    path("painel/produtos/<int:id>/editar/", views.painel_produto_form, name="painel_produto_editar"),
    path("painel/produtos/<int:id>/excluir/", views.painel_produto_excluir, name="painel_produto_excluir"),
    path("painel/categorias/", views.painel_categorias, name="painel_categorias"),
    path("painel/categorias/nova/", views.painel_categoria_salvar, name="painel_categoria_nova"),
    path("painel/categorias/<int:id>/editar/", views.painel_categoria_salvar, name="painel_categoria_editar"),
    path("painel/categorias/<int:id>/excluir/", views.painel_categoria_excluir, name="painel_categoria_excluir"),
    path("painel/pedidos/", views.painel_pedidos, name="painel_pedidos"),
]