from django.contrib import admin

from .models import Categoria, Pedido, Produto

# Admin pronto do Django em /admin/ (útil para conferir o banco; o painel da loja fica em /painel/)
admin.site.register(Categoria)
admin.site.register(Produto)
admin.site.register(Pedido)
