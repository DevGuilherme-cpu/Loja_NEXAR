from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import CadastroForm
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


# ---------- conta (login / cadastro / sair) ----------

class Entrar(LoginView):
    # LoginView já valida o "next" (só aceita URL do próprio site) e mostra form.errors
    template_name = "login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, f"Olá, {form.get_user().get_username()}! Você entrou na sua conta.")
        return super().form_valid(form)


class Sair(LogoutView):
    # Padrão do Django: só aceita POST (GET devolve 405). Redireciona para LOGOUT_REDIRECT_URL.
    def post(self, request, *args, **kwargs):
        resposta = super().post(request, *args, **kwargs)
        messages.info(request, "Você saiu da sua conta.")  # depois do logout: a sessão nova guarda a mensagem
        return resposta


def destino_seguro(request):
    """Mesmo critério do LoginView: o "next" só vale se for do próprio site."""
    nxt = request.POST.get("next") or request.GET.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return nxt
    return settings.LOGIN_REDIRECT_URL


def cadastro(request):
    if request.user.is_authenticated:
        return redirect("loja:index")
    form = CadastroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, f"Conta criada! Bem-vindo(a), {user.username}.")
        return redirect(destino_seguro(request))
    return render(request, "cadastro.html", {"form": form, "next": request.POST.get("next") or request.GET.get("next", "")})


# ---------- painel admin ----------
# A LEITURA já vem do banco. shortcut: salvar/excluir ainda não gravam nada.
# Eliton: fazer o CRUD de verdade (INSERT/UPDATE/DELETE).
# Todas as views do painel exigem usuário staff (is_staff + ativo):
#  - visitante  -> /entrar/?next=... (padrão do staff_member_required)
#  - cliente logado sem is_staff -> home com mensagem de erro. Não dá para usar só o padrão
#    (mandar para /entrar/?next=/painel/): o LoginView com redirect_authenticated_user=True
#    devolveria o cliente para o painel, que o mandaria para o login de novo (loop).
def somente_staff(view):
    protegida = staff_member_required(view, login_url="loja:entrar")

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and not (request.user.is_active and request.user.is_staff):
            messages.error(request, "Acesso restrito à equipe da loja.")
            return redirect("loja:index")
        return protegida(request, *args, **kwargs)
    return wrapper


@somente_staff
def painel_produtos(request):
    busca = request.GET.get("busca", "").strip()
    return render(request, "painel/produtos.html", {"produtos": filtrar(busca), "busca": busca})


@somente_staff
def painel_produto_form(request, id=None):
    produto = get_object_or_404(PRODUTOS, id=id) if id is not None else None
    if request.method == "POST":
        messages.info(request, "Salvar simulado: ainda não grava no banco.")
        return redirect("loja:painel_produtos")
    return render(request, "painel/produto_form.html", {"produto": produto})


@somente_staff
@require_POST
def painel_produto_excluir(request, id):
    messages.error(request, "Exclusão simulada: ainda não apaga do banco.")
    return redirect("loja:painel_produtos")


@somente_staff
def painel_categorias(request):
    # SELECT categorias.*, COUNT(produtos.id) ... LEFT JOIN produtos ... GROUP BY categorias.id
    lista = Categoria.objects.annotate(total=Count("produto"))
    return render(request, "painel/categorias.html", {"lista": lista})


@somente_staff
@require_POST
def painel_categoria_salvar(request, id=None):  # sem id = nova, com id = editar
    messages.info(request, "Salvar simulado: ainda não grava no banco.")
    return redirect("loja:painel_categorias")


@somente_staff
@require_POST
def painel_categoria_excluir(request, id):
    messages.error(request, "Exclusão simulada: ainda não apaga do banco.")
    return redirect("loja:painel_categorias")


@somente_staff
def painel_pedidos(request):
    # O JOIN do trabalho: pedidos + auth_user + produtos + categorias numa consulta só
    pedidos = Pedido.objects.select_related("usuario", "produto__categoria")
    return render(request, "painel/pedidos.html", {"pedidos": pedidos})