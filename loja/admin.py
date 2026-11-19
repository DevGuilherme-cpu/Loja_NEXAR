from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .forms import AdminCriarUsuarioForm, AdminEditarUsuarioForm
from .models import Categoria, Pedido, Produto

admin.site.register(Categoria)
admin.site.register(Produto)


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "produto", "quantidade", "preco_unitario", "data")
    list_select_related = ("usuario", "produto")

    def get_readonly_fields(self, request, obj=None):
        # Na criação pode ficar vazio (Pedido.save() copia o preço do produto);
        # depois de gravado, o preço da compra não muda pelo admin.
        campos = super().get_readonly_fields(request, obj)
        # entrega, frete e pagamento vêm do checkout: a equipe consulta, mas não altera (nem o CPF mascarado)
        campos = (*campos, "entrega_nome", "entrega_cpf", "entrega_telefone", "entrega_cep", "entrega_endereco",
                  "entrega_bairro", "entrega_cidade", "entrega_uf", "envio", "pagamento", "frete")
        return (*campos, "preco_unitario") if obj is not None else campos


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
