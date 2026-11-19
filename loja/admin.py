from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .forms import AdminCriarUsuarioForm, AdminEditarUsuarioForm
from .models import Categoria, ItemPedido, Pedido, Produto

admin.site.register(Categoria)
admin.site.register(Produto)


class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 1

    def get_readonly_fields(self, request, obj=None):
        # Item novo: o preço pode ficar vazio (ItemPedido.save() copia o do produto).
        # Item já gravado: o preço da compra não muda pelo admin.
        campos = super().get_readonly_fields(request, obj)
        return (*campos, "preco_unitario") if obj is not None else campos


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "resumo", "data")
    list_select_related = ("usuario",)
    inlines = [ItemPedidoInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("itens__produto")

    def get_readonly_fields(self, request, obj=None):
        campos = super().get_readonly_fields(request, obj)
        # entrega, frete e pagamento vêm do checkout: a equipe consulta, mas não altera (nem o CPF mascarado)
        return (*campos, "entrega_nome", "entrega_cpf", "entrega_telefone", "entrega_cep", "entrega_endereco",
                "entrega_bairro", "entrega_cidade", "entrega_uf", "envio", "pagamento", "frete")


# Usuários: mesmo UserAdmin do Django, só trocando os forms para aplicar a política de e-mail
admin.site.unregister(User)


@admin.register(User)
class NexarUserAdmin(UserAdmin):
    form = AdminEditarUsuarioForm
    add_form = AdminCriarUsuarioForm
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "usable_password", "password1", "password2"),
        }),
    )
