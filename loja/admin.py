from django.contrib import admin

from .models import Categoria, Pedido, Produto

admin.site.register(Categoria)
admin.site.register(Produto)
admin.site.register(Pedido)
