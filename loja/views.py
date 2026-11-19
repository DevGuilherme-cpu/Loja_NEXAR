import uuid
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Count, F, ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import (CATEGORIA_REPETIDA, EMAIL_REPETIDO, FRETE_GRATIS_ACIMA, CadastroForm, CategoriaForm, EntregaForm,
                    ProdutoForm, calcular_frete, email_em_uso, uploads_habilitados)
from .assistente import SUGESTOES, responder
from .models import Categoria, Pedido, Produto
from .painel import CD, PERIODOS, entregas, resumo  # entregas/CD também desenham o rastreio do cliente
from .simulacao import simular_pedidos

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


QTD_MAX_POR_PEDIDO = 10
SESSAO_TOKENS = "pedido_tokens"


def novo_token_pedido(request):
    """Token de uso único por formulário: evita gravar o mesmo pedido duas vezes (F5 / clique duplo)."""
    token = uuid.uuid4().hex
    tokens = request.session.get(SESSAO_TOKENS, [])[-19:]  # guarda no máximo 20 formulários abertos
    request.session[SESSAO_TOKENS] = tokens + [token]
    return token


def consumir_token_pedido(request, token):
    tokens = request.session.get(SESSAO_TOKENS, [])
    if not token or token not in tokens:
        return False
    tokens.remove(token)
    request.session[SESSAO_TOKENS] = tokens
    return True


def devolver_token_pedido(request, token):
    """Compra recusada depois de consumir o token (sem estoque): o mesmo formulário pode ser reenviado."""
    tokens = request.session.get(SESSAO_TOKENS, [])
    if token not in tokens:
        request.session[SESSAO_TOKENS] = (tokens + [token])[-20:]


def inteiro_ascii(texto):
    """Só 0-9: str.isdigit() aceita "²" e "١", que fariam int() falhar ou aceitar dígitos estranhos."""
    # len <= 9: o Python recusa int() de textos com mais de 4300 dígitos (seria erro 500)
    return texto.isascii() and texto.isdigit() and len(texto) <= 9


def produto(request, id):
    contexto = {"produto": get_object_or_404(PRODUTOS, id=id)}
    if request.user.is_authenticated:
        contexto["token_pedido"] = novo_token_pedido(request)
    return render(request, "produto.html", contexto)


SESSAO_CHECKOUT = "checkout"


def contexto_checkout(request, produto, tamanho, quantidade, form, token=None):
    subtotal = produto.preco * quantidade
    return {"produto": produto, "tamanho": tamanho, "quantidade": quantidade, "form": form,
            "token_pedido": token or novo_token_pedido(request), "subtotal": subtotal,
            "frete_padrao": calcular_frete(subtotal, "padrao"), "frete_expresso": calcular_frete(subtotal, "expresso"),
            "falta_frete_gratis": FRETE_GRATIS_ACIMA - subtotal}


def checkout(request):
    """O botão Comprar traz para cá: entrega, frete e pagamento (simulado) antes de gravar o pedido.

    POST (da página do produto): guarda a escolha na sessão e redireciona, para o F5 não reenviar.
    GET: mostra o formulário. Quem não entrou vai para o login e volta para cá sem perder a escolha.
    O pedido é gravado pela view pedido(), com as mesmas validações e a mesma baixa de estoque.
    """
    destino = f"{reverse('loja:entrar')}?next={reverse('loja:checkout')}"
    if request.method == "POST":
        request.session[SESSAO_CHECKOUT] = {k: request.POST.get(k, "") for k in ("produto_id", "tamanho", "quantidade")}
        if not request.user.is_authenticated:
            messages.info(request, "Entre na sua conta para finalizar a compra.")
            return redirect(destino)
        return redirect("loja:checkout")
    if not request.user.is_authenticated:
        return redirect(destino)

    escolha = request.session.get(SESSAO_CHECKOUT) or {}
    produto_id, tamanho, quantidade = (escolha.get(k, "") for k in ("produto_id", "tamanho", "quantidade"))
    produto = Produto.objects.select_related("categoria").filter(id=int(produto_id)).first() \
        if inteiro_ascii(produto_id) else None
    if produto is None:
        messages.info(request, "Escolha uma peça para comprar.")
        return redirect("loja:produtos")
    if tamanho not in produto.tamanhos:
        messages.error(request, "Escolha um tamanho válido.")
        return redirect("loja:produto", id=produto.id)
    if not inteiro_ascii(quantidade) or not 1 <= int(quantidade) <= QTD_MAX_POR_PEDIDO:
        messages.error(request, f"A quantidade deve ser um número de 1 a {QTD_MAX_POR_PEDIDO}.")
        return redirect("loja:produto", id=produto.id)
    form = EntregaForm(initial={"nome": request.user.get_full_name(), "envio": "padrao", "pagamento": "pix"})
    return render(request, "checkout.html", contexto_checkout(request, produto, tamanho, int(quantidade), form))


@login_required
def pedido_confirmado(request, id):
    pedido = get_object_or_404(Pedido.objects.select_related("produto__categoria"), id=id, usuario=request.user)
    dias = (1, 3) if pedido.envio == "expresso" else (3, 8)
    base = timezone.localdate(pedido.data)
    # rastreio simulado e acelerado (o mesmo de static/js/mapa.js): separa em 45 s, viaja em 315 s
    segundos = (timezone.now() - pedido.data).total_seconds()
    etapa = 2 if segundos < 45 else 3 if segundos < 360 else 4
    return render(request, "pedido_confirmado.html", {
        "pedido": pedido, "etapa": etapa, "entregas": entregas([pedido]), "cd": CD,
        "chega_de": base + timedelta(days=dias[0]), "chega_ate": base + timedelta(days=dias[1]),
    })


@require_POST
def pedido(request):
    """Compra de um produto: grava o pedido e baixa o estoque na mesma transação.

    Tudo é validado no servidor (o HTML pode ser alterado). O preço vem do banco e fica gravado
    em preco_unitario. A baixa de estoque é um UPDATE condicional (WHERE estoque >= quantidade):
    duas compras simultâneas da última peça não passam as duas, em SQLite, PostgreSQL e MySQL.
    """
    produto_id = request.POST.get("produto_id", "")
    if not inteiro_ascii(produto_id):
        messages.error(request, "Produto inválido.")
        return redirect("loja:produtos")
    produto = get_object_or_404(Produto, id=int(produto_id))
    volta = redirect("loja:produto", id=produto.id)

    if not request.user.is_authenticated:
        messages.info(request, "Entre na sua conta para comprar.")
        return redirect(f"{reverse('loja:entrar')}?next={reverse('loja:produto', args=[produto.id])}")

    # O campo "personalizacao" do formulário é ignorado de propósito: Pedido não tem coluna para ele
    # (a personalização 3D é só visual). Campos extras como "preco" também são ignorados.
    tamanho = request.POST.get("tamanho", "")
    quantidade = request.POST.get("quantidade", "").strip()
    if tamanho not in produto.tamanhos:  # tênis só aceita 38 a 44, boné só "U"...
        messages.error(request, "Escolha um tamanho válido.")
        return volta
    if not inteiro_ascii(quantidade) or not 1 <= int(quantidade) <= QTD_MAX_POR_PEDIDO:
        messages.error(request, f"A quantidade deve ser um número de 1 a {QTD_MAX_POR_PEDIDO}.")
        return volta
    quantidade = int(quantidade)

    # vindo do checkout: entrega e pagamento são obrigatórios; com erro, a página volta com os avisos
    # (antes de consumir o token, para a pessoa corrigir e enviar de novo)
    entrega = EntregaForm(request.POST) if request.POST.get("checkout") else None
    if entrega and not entrega.is_valid():
        return render(request, "checkout.html",
                      contexto_checkout(request, produto, tamanho, quantidade, entrega, request.POST.get("token_pedido")))

    # depois das validações: um formulário inválido pode ser corrigido e reenviado com o mesmo token
    token = request.POST.get("token_pedido")
    if not consumir_token_pedido(request, token):
        messages.warning(request, "Este pedido já foi enviado ou a página expirou. Confira em Pedidos antes de comprar de novo.")
        return volta

    with transaction.atomic():
        baixou = Produto.objects.filter(id=produto.id, estoque__gte=quantidade).update(
            estoque=F("estoque") - quantidade)
        if not baixou:
            # first(): o produto pode ter sido excluído entre o get_object_or_404 e o UPDATE
            estoque = Produto.objects.filter(id=produto.id).values_list("estoque", flat=True).first()
            if estoque is None:
                messages.error(request, "Este produto não está mais disponível.")
                return redirect("loja:produtos")
            devolver_token_pedido(request, token)  # pode corrigir a quantidade e reenviar
            messages.error(request, "Produto esgotado." if estoque == 0 else
                           f"Só restam {estoque} unidade(s) de “{produto.nome}”.")
            return volta
        # mesma transação do UPDATE: a linha já está bloqueada, o preço lido é o atual
        preco = Produto.objects.filter(id=produto.id).values_list("preco", flat=True).get()
        novo = Pedido.objects.create(usuario=request.user, produto=produto, tamanho=tamanho,
                                     quantidade=quantidade, preco_unitario=preco,
                                     **(entrega.dados_do_pedido(preco * quantidade) if entrega else {}))
    if entrega:
        request.session.pop(SESSAO_CHECKOUT, None)
        return redirect("loja:pedido_confirmado", id=novo.id)
    total = f"{novo.total:.2f}".replace(".", ",")
    messages.success(request, f"Pedido #{novo.id} confirmado: {quantidade}× {produto.nome} ({tamanho}) — R$ {total}.")
    return volta


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


def explicar_colisao(form):
    """IntegrityError no cadastro: descobre qual campo colidiu e mostra no formulário."""
    username = form.cleaned_data.get("username")
    email = form.cleaned_data.get("email")
    if username and User.objects.filter(username=username).exists():
        form.add_error("username", "Já existe um usuário com este nome.")
    elif email and email_em_uso(email):
        form.add_error("email", EMAIL_REPETIDO)
    else:
        form.add_error(None, "Não foi possível criar a conta. Tente novamente.")


def cadastro(request):
    if request.user.is_authenticated:
        return redirect("loja:index")
    form = CadastroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            # Duas pessoas podem passar pela validação ao mesmo tempo com o mesmo e-mail/usuário:
            # quem garante é o banco (índice único). atomic() desfaz só este INSERT.
            with transaction.atomic():
                user = form.save()
        except IntegrityError:
            explicar_colisao(form)
        else:
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, f"Conta criada! Bem-vindo(a), {user.username}.")
            return redirect(destino_seguro(request))
    return render(request, "cadastro.html", {"form": form, "next": request.POST.get("next") or request.GET.get("next", "")})


@login_required
def conta(request):
    pedidos = Pedido.objects.filter(usuario=request.user).select_related("produto")
    return render(request, "conta.html", {"pedidos": pedidos})


@login_required
@require_POST
def conta_encerrar(request):
    """Encerra a conta pelo próprio site, sem precisar falar com ninguém.

    Quem nunca comprou é apagado. Quem tem pedidos fica anonimizado e desativado: o pedido é
    documento da venda (Pedido.usuario é PROTECT), mas sem nome, e-mail nem senha.
    """
    usuario = request.user
    if usuario.is_staff:
        messages.error(request, "Contas da equipe são encerradas pelo administrador da loja.")
        return redirect("loja:conta")
    if not usuario.check_password(request.POST.get("senha", "")):
        messages.error(request, "Senha incorreta. A conta não foi encerrada.")
        return redirect("loja:conta")

    protocolo = f"NX-{timezone.localdate():%Y%m%d}-{usuario.pk}"
    logout(request)
    if Pedido.objects.filter(usuario=usuario).exists():
        usuario.username = f"conta-encerrada-{usuario.pk}"
        usuario.email = usuario.first_name = usuario.last_name = ""
        usuario.is_active = False
        usuario.set_unusable_password()
        usuario.save()
    else:
        usuario.delete()
    messages.success(request, f"Sua conta foi encerrada e seus dados pessoais foram apagados. Protocolo {protocolo}.")
    return redirect("loja:index")


# Painel (CRUD de produtos e categorias pelo ORM)
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
def painel_inicio(request):
    dias = int(request.GET["dias"]) if request.GET.get("dias") in {str(p) for p in PERIODOS} else 30
    return render(request, "painel/inicio.html",
                  resumo(dias) | {"dias": dias, "periodos": PERIODOS, "sugestoes": SUGESTOES})


@somente_staff
@require_POST
def painel_assistente(request):
    resposta = responder(request.POST.get("pergunta", "")[:300])
    if request.headers.get("X-Requested-With") == "fetch":
        return JsonResponse({"resposta": resposta})
    messages.info(request, resposta)  # sem JavaScript: mostra a resposta como aviso na visão geral
    return redirect("loja:painel_inicio")


@somente_staff
@require_POST
def painel_simular(request):
    criados = simular_pedidos()
    if criados:
        messages.success(request, f"{len(criados)} pedidos de exemplo criados. Veja o mapa em Pedidos.")
    else:
        messages.error(request, "Todos os produtos estão esgotados: aumente o estoque para simular vendas.")
    return redirect("loja:painel_inicio")


@somente_staff
def painel_produtos(request):
    busca = request.GET.get("busca", "").strip()
    categoria = request.GET.get("categoria", "")
    return render(request, "painel/produtos.html",
                  {"produtos": filtrar(busca, categoria), "busca": busca, "categoria": categoria})


def link_arquivo(arquivo):
    """(nome, url) do arquivo atual de um campo, ou None. Aceita caminho /static/... e link http(s)."""
    if not arquivo:
        return None
    nome = arquivo.name
    if nome.startswith(("/", "http://", "https://")):
        url = nome  # valores fixos (/static/modelos/...) ou links externos: como estão
    else:
        url = arquivo.url  # arquivo enviado: a URL vem do storage configurado (não MEDIA_URL + nome)
    return nome.rsplit("/", 1)[-1], url


@somente_staff
def painel_produto_form(request, id=None):
    produto = get_object_or_404(PRODUTOS, id=id) if id is not None else None
    form = ProdutoForm(request.POST or None, request.FILES or None, instance=produto)
    if request.method == "POST" and form.is_valid():
        try:
            # INSERT (novo) ou UPDATE (edição). Os uploads são gravados no storage ANTES do INSERT/UPDATE.
            # O atomic desfaz só o banco: se o banco falhar depois, o arquivo já gravado fica órfão no
            # storage (não há limpeza automática; pode ser apagado à mão em media/).
            with transaction.atomic():
                salvo = form.save()
        except OSError:  # disco cheio, sem permissão, sistema de arquivos somente leitura...
            form.add_error(None, "Não foi possível gravar os arquivos enviados. Nada foi salvo; tente de novo "
                                 "ou salve sem anexos.")
        except DatabaseError:
            form.add_error(None, "Erro ao salvar no banco de dados. Nada foi salvo; tente de novo.")
        else:
            acao = "atualizado" if produto else "cadastrado"
            messages.success(request, f"Produto “{salvo.nome}” {acao}.")
            return redirect("loja:painel_produtos")
    # GET ou POST inválido (200 com os erros e o que foi digitado no form).
    # O is_valid() altera a instância em memória: a prévia e os arquivos atuais vêm do banco.
    if produto is not None and form.is_bound:
        produto = get_object_or_404(PRODUTOS, id=id)
    atuais = {campo: link_arquivo(getattr(produto, campo)) if produto else None
              for campo in ("imagem", "imagem_2", "modelo_3d")}
    return render(request, "painel/produto_form.html", {"produto": produto, "form": form, "atuais": atuais,
                                                        "uploads_habilitados": uploads_habilitados()})


@somente_staff
@require_POST
def painel_produto_excluir(request, id):
    produto = get_object_or_404(Produto, id=id)
    try:
        produto.delete()  # DELETE; arquivos de mídia ficam no disco
    except ProtectedError:  # Pedido.produto é PROTECT
        total = produto.pedido_set.count()
        messages.error(request, f"O produto “{produto.nome}” tem {total} pedido(s) e não pode ser excluído. "
                                "Para tirá-lo de venda, zere o estoque.")
    else:
        messages.success(request, f"Produto “{produto.nome}” excluído.")
    return redirect("loja:painel_produtos")


@somente_staff
def painel_categorias(request):
    # prefetch: as fotos dos produtos de cada categoria saem numa consulta só
    lista = Categoria.objects.annotate(total=Count("produto")).prefetch_related("produto_set")
    return render(request, "painel/categorias.html", {"lista": lista})


@somente_staff
@require_POST
def painel_categoria_salvar(request, id=None):  # sem id = nova
    categoria = get_object_or_404(Categoria, id=id) if id is not None else None
    antigo = categoria.nome if categoria else None
    form = CategoriaForm(request.POST, instance=categoria)
    if not form.is_valid():
        erros = " ".join(e for lista in form.errors.values() for e in lista)
        messages.error(request, f"Categoria não salva: {erros}")
        return redirect("loja:painel_categorias")
    try:
        with transaction.atomic():  # corrida: o índice único do banco decide
            salva = form.save()  # INSERT ou UPDATE
    except IntegrityError:
        messages.error(request, f"Categoria não salva: {CATEGORIA_REPETIDA}")
    else:
        if antigo is None:
            messages.success(request, f"Categoria “{salva.nome}” criada.")
        else:
            messages.success(request, f"Categoria “{antigo}” renomeada para “{salva.nome}”.")
    return redirect("loja:painel_categorias")


@somente_staff
@require_POST
def painel_categoria_excluir(request, id):
    categoria = get_object_or_404(Categoria, id=id)
    try:
        categoria.delete()  # DELETE
    except ProtectedError:  # Produto.categoria é PROTECT
        total = categoria.produto_set.count()
        messages.error(request, f"A categoria “{categoria.nome}” tem {total} produto(s) e não pode ser excluída. "
                                "Mova ou exclua esses produtos antes.")
    else:
        messages.success(request, f"Categoria “{categoria.nome}” excluída.")
    return redirect("loja:painel_categorias")


@somente_staff
def painel_pedidos(request):
    # JOIN pedidos + usuário + produto + categoria
    pedidos = Pedido.objects.select_related("usuario", "produto__categoria")
    return render(request, "painel/pedidos.html",
                  {"pedidos": pedidos, "entregas": entregas(pedidos[:12]), "cd": CD})