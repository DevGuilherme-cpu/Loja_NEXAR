import uuid
from datetime import datetime, timedelta
from decimal import Decimal
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
from .models import Categoria, ItemPedido, Pedido, Produto
from .grupos import CLIENTES, FUNCIONARIOS
from .painel import (CD, PERIODOS, entregas, estoque, financas, ranking_clientes,  # entregas/CD: rastreio do cliente
                     resumo)
from .simulacao import simular_pedidos

# produtos já com a categoria (JOIN)
PRODUTOS = Produto.objects.select_related("categoria")


def filtrar(busca, categoria=""):
    lista = PRODUTOS.filter(nome__icontains=busca)
    return lista.filter(categoria_id=categoria) if categoria.isdigit() else lista


# fim do drop da home (data fixa: a contagem é de verdade, não reinicia a cada visita)
FIM_DROP = datetime(2026, 11, 30, 23, 59, 59)


def index(request):
    fim = timezone.make_aware(FIM_DROP)
    return render(request, "index.html", {
        "destaques": PRODUTOS[:4],
        # peça em destaque do drop: a com menos unidades (o "restam X" vem do estoque real)
        "drop": PRODUTOS.filter(estoque__gt=0).order_by("estoque", "id").first() if timezone.now() < fim else None,
        "fim_drop": fim,
        "looks": PRODUTOS.exclude(imagem_2="")[:5],
    })


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


SESSAO_ANIMAR = "animar_pedido"  # id do pedido recém-criado: a animação da caixa toca uma vez só

# Sacola: fica na sessão, como [{"produto_id": 3, "tamanho": "M", "quantidade": 2}, ...].
# Serve para visitante e para quem tem conta, e continua depois do login (a sessão é a mesma).
# Preço e estoque não ficam guardados: são lidos do banco a cada página e conferidos de novo ao gravar.
SESSAO_SACOLA = "sacola"
MAX_LINHAS_SACOLA = 20


def erro_da_escolha(produto, tamanho, quantidade):
    """Mensagem de erro do tamanho/quantidade escolhidos, ou None se estiver tudo certo."""
    if tamanho not in produto.tamanhos:  # tênis só aceita 38 a 44, boné só "U"...
        return "Escolha um tamanho válido."
    if not inteiro_ascii(quantidade) or not 1 <= int(quantidade) <= QTD_MAX_POR_PEDIDO:
        return f"A quantidade deve ser um número de 1 a {QTD_MAX_POR_PEDIDO}."
    return None


def ler_escolha(dados):
    """Produto, tamanho e quantidade de um formulário da loja.

    Devolve (produto, tamanho, quantidade, erro). erro é None quando está tudo certo; produto pode
    vir preenchido mesmo com erro (para voltar à página dele).
    """
    produto_id, tamanho = dados.get("produto_id", ""), dados.get("tamanho", "")
    quantidade = dados.get("quantidade", "").strip()
    produto = PRODUTOS.filter(id=int(produto_id)).first() if inteiro_ascii(produto_id) else None
    if produto is None:
        return None, tamanho, 0, "Produto inválido."
    erro = erro_da_escolha(produto, tamanho, quantidade)
    return produto, tamanho, 0 if erro else int(quantidade), erro


def itens_da_sacola(request):
    """[(produto, tamanho, quantidade)] da sessão. Peça que saiu do catálogo some da sacola."""
    linhas = request.session.get(SESSAO_SACOLA, [])
    produtos = PRODUTOS.in_bulk([linha["produto_id"] for linha in linhas])
    return [(produtos[linha["produto_id"]], linha["tamanho"], linha["quantidade"]) for linha in linhas
            if linha["produto_id"] in produtos and linha["tamanho"] in produtos[linha["produto_id"]].tamanhos]


def guardar_sacola(request, itens):
    request.session[SESSAO_SACOLA] = [{"produto_id": p.id, "tamanho": t, "quantidade": q} for p, t, q in itens]


def por_na_sacola(request, produto, tamanho, quantidade):
    """Soma com a mesma peça e tamanho, se já estiver lá. Devolve a mensagem de erro, ou None."""
    itens = itens_da_sacola(request)
    for i, (p, t, q) in enumerate(itens):
        if p.id == produto.id and t == tamanho:
            itens[i] = (p, t, min(q + quantidade, QTD_MAX_POR_PEDIDO))
            break
    else:
        if len(itens) >= MAX_LINHAS_SACOLA:
            return f"A sacola aceita até {MAX_LINHAS_SACOLA} peças diferentes. Finalize esta compra primeiro."
        itens.append((produto, tamanho, quantidade))
    guardar_sacola(request, itens)
    return None


def contexto_sacola(itens):
    linhas = [{"produto": p, "tamanho": t, "quantidade": q, "total": p.preco * q, "chave": f"{p.id}-{t}"}
              for p, t, q in itens]
    subtotal = sum((linha["total"] for linha in linhas), Decimal(0))
    return {"linhas": linhas, "subtotal": subtotal, "pecas": sum(q for _, _, q in itens),
            "falta_frete_gratis": FRETE_GRATIS_ACIMA - subtotal,
            "frete_gratis_pct": min(100, round(subtotal / FRETE_GRATIS_ACIMA * 100))}


def sacola(request):
    itens = itens_da_sacola(request)
    if len(itens) != len(request.session.get(SESSAO_SACOLA, [])):
        guardar_sacola(request, itens)  # tira da sessão o que saiu do catálogo
    return render(request, "sacola.html", contexto_sacola(itens))


@require_POST
def sacola_adicionar(request):
    """Botão "Adicionar à sacola". Com JavaScript responde em JSON (a página não recarrega)."""
    produto, tamanho, quantidade, erro = ler_escolha(request.POST)
    erro = erro or por_na_sacola(request, produto, tamanho, quantidade)
    via_js = request.headers.get("X-Requested-With") == "fetch"
    if erro:
        if via_js:
            return JsonResponse({"ok": False, "mensagem": erro}, status=400)
        messages.error(request, erro)
        return redirect("loja:produto", id=produto.id) if produto else redirect("loja:produtos")
    mensagem = f"{produto.nome} ({tamanho}) está na sacola."
    if via_js:
        pecas = sum(q for _, _, q in itens_da_sacola(request))
        return JsonResponse({"ok": True, "mensagem": mensagem, "pecas": pecas})
    messages.success(request, mensagem)
    return redirect("loja:produto", id=produto.id)


@require_POST
def sacola_atualizar(request):
    """Muda a quantidade de uma peça da sacola (linha = "produto-tamanho"); 0 tira a peça."""
    itens = itens_da_sacola(request)
    linha, quantidade = request.POST.get("linha", ""), request.POST.get("quantidade", "").strip()
    for i, (p, t, _) in enumerate(itens):
        if f"{p.id}-{t}" == linha and inteiro_ascii(quantidade):
            if int(quantidade):
                itens[i] = (p, t, min(int(quantidade), QTD_MAX_POR_PEDIDO))
            else:
                del itens[i]
                messages.info(request, f"{p.nome} ({t}) saiu da sacola.")
            guardar_sacola(request, itens)
            break
    return redirect("loja:sacola")


def contexto_checkout(request, itens, form, token=None):
    contexto = contexto_sacola(itens)
    subtotal = contexto["subtotal"]
    return contexto | {"form": form, "token_pedido": token or novo_token_pedido(request),
                       "frete_padrao": calcular_frete(subtotal, "padrao"),
                       "frete_expresso": calcular_frete(subtotal, "expresso")}


def checkout(request):
    """Entrega, frete e pagamento (simulado) das peças da sacola, antes de gravar o pedido.

    POST (botão Comprar da página do produto): põe a peça na sacola e redireciona, para o F5 não reenviar.
    GET: mostra o formulário. Não precisa de conta: quem não entrou compra como visitante (pede
    e-mail) ou clica em "Entrar" e volta para cá sem perder a sacola (a sessão continua no login).
    O pedido é gravado pela view pedido(), com as mesmas validações e a mesma baixa de estoque.
    """
    if request.method == "POST":
        produto, tamanho, quantidade, erro = ler_escolha(request.POST)
        erro = erro or por_na_sacola(request, produto, tamanho, quantidade)
        if erro:
            messages.error(request, erro)
            return redirect("loja:produto", id=produto.id) if produto else redirect("loja:produtos")
        return redirect("loja:checkout")

    itens = itens_da_sacola(request)
    if not itens:
        messages.info(request, "Sua sacola está vazia. Escolha uma peça para comprar.")
        return redirect("loja:produtos")
    visitante = not request.user.is_authenticated
    nome = "" if visitante else request.user.get_full_name()
    form = EntregaForm(initial={"nome": nome, "envio": "padrao", "pagamento": "pix"}, visitante=visitante)
    return render(request, "checkout.html", contexto_checkout(request, itens, form))


# pedido com as peças, os produtos e as categorias (3 consultas, em vez de uma por peça)
PEDIDOS = Pedido.objects.select_related("usuario").prefetch_related("itens__produto__categoria")


@login_required
def pedido_confirmado(request, id):
    pedido = get_object_or_404(PEDIDOS, id=id, usuario=request.user)
    return pagina_do_pedido(request, pedido)


def pedido_acompanhar(request, codigo):
    """Pedido aberto pelo link secreto (compra sem conta). Só quem tem o link vê: o código tem 128 bits."""
    pedido = get_object_or_404(PEDIDOS, codigo=codigo)
    return pagina_do_pedido(request, pedido, link=request.build_absolute_uri())


def pagina_do_pedido(request, pedido, link=None):
    dias = (1, 3) if pedido.envio == "expresso" else (3, 8)
    base = timezone.localdate(pedido.data)
    # rastreio simulado e acelerado (o mesmo de static/js/mapa.js): separa em 45 s, viaja em 315 s
    segundos = (timezone.now() - pedido.data).total_seconds()
    etapa = 2 if segundos < 45 else 3 if segundos < 360 else 4
    # pop: ao atualizar a página a animação não toca de novo
    animar = request.session.pop(SESSAO_ANIMAR, None) == pedido.id
    return render(request, "pedido_confirmado.html", {
        "pedido": pedido, "etapa": etapa, "entregas": entregas([pedido]), "cd": CD, "link": link, "animar": animar,
        "chega_de": base + timedelta(days=dias[0]), "chega_ate": base + timedelta(days=dias[1]),
    })


class SemEstoque(Exception):
    """Uma das peças acabou no meio da compra: desfaz a transação inteira (nenhum estoque baixa)."""

    def __init__(self, produto):
        super().__init__(produto.nome)
        self.produto = produto


@require_POST
def pedido(request):
    """Grava o pedido e baixa o estoque de todas as peças na mesma transação.

    Pelo checkout (checkout=1): as peças vêm da sacola, com entrega e pagamento. Sem o checkout
    (compra direta de uma peça, para quem tem conta): a peça vem do formulário.
    Tudo é validado no servidor (o HTML pode ser alterado). O preço vem do banco e fica gravado
    em preco_unitario. A baixa de estoque é um UPDATE condicional (WHERE estoque >= quantidade):
    duas compras simultâneas da última peça não passam as duas, em SQLite, PostgreSQL e MySQL.
    """
    visitante = not request.user.is_authenticated
    pelo_checkout = bool(request.POST.get("checkout"))
    if pelo_checkout:
        itens = itens_da_sacola(request)
        if not itens:
            messages.info(request, "Sua sacola está vazia. Escolha uma peça para comprar.")
            return redirect("loja:produtos")
        volta = redirect("loja:sacola")
    else:
        produto_id = request.POST.get("produto_id", "")
        if not inteiro_ascii(produto_id):
            messages.error(request, "Produto inválido.")
            return redirect("loja:produtos")
        produto = get_object_or_404(Produto, id=int(produto_id))
        # compra direta (sem o checkout) continua exigindo conta; pelo checkout dá para comprar sem conta
        if visitante:
            messages.info(request, "Entre na sua conta para comprar.")
            return redirect(f"{reverse('loja:entrar')}?next={reverse('loja:produto', args=[produto.id])}")
        # O campo "personalizacao" do formulário é ignorado de propósito: o pedido não tem coluna para ele
        # (a personalização 3D é só visual). Campos extras como "preco" também são ignorados.
        tamanho, quantidade = request.POST.get("tamanho", ""), request.POST.get("quantidade", "").strip()
        volta = redirect("loja:produto", id=produto.id)
        if erro := erro_da_escolha(produto, tamanho, quantidade):
            messages.error(request, erro)
            return volta
        itens = [(produto, tamanho, int(quantidade))]

    # vindo do checkout: entrega e pagamento são obrigatórios; com erro, a página volta com os avisos
    # (antes de consumir o token, para a pessoa corrigir e enviar de novo)
    entrega = EntregaForm(request.POST, visitante=visitante) if pelo_checkout else None
    if entrega and not entrega.is_valid():
        return render(request, "checkout.html",
                      contexto_checkout(request, itens, entrega, request.POST.get("token_pedido")))

    # depois das validações: um formulário inválido pode ser corrigido e reenviado com o mesmo token
    token = request.POST.get("token_pedido")
    if not consumir_token_pedido(request, token):
        messages.warning(request, "Este pedido já foi enviado ou a página expirou. Confira em Pedidos antes de comprar de novo.")
        return volta

    try:
        with transaction.atomic():
            # sempre na ordem do id: duas compras com as mesmas peças não ficam uma esperando a outra
            for produto, _, qtd in sorted(itens, key=lambda i: i[0].id):
                if not Produto.objects.filter(id=produto.id, estoque__gte=qtd).update(estoque=F("estoque") - qtd):
                    raise SemEstoque(produto)
            # mesma transação do UPDATE: as linhas já estão bloqueadas, o preço lido é o atual
            precos = dict(Produto.objects.filter(id__in={p.id for p, _, _ in itens}).values_list("id", "preco"))
            subtotal = sum(precos[p.id] * q for p, _, q in itens)
            dados = entrega.dados_do_pedido(subtotal) if entrega else {}
            if entrega and not visitante and not dados["entrega_email"]:
                dados["entrega_email"] = request.user.email
            novo = Pedido.objects.create(usuario=None if visitante else request.user, **dados)
            ItemPedido.objects.bulk_create([ItemPedido(pedido=novo, produto=p, tamanho=t, quantidade=q,
                                                       preco_unitario=precos[p.id]) for p, t, q in itens])
    except SemEstoque as falta:
        # first(): o produto pode ter sido excluído entre a leitura e o UPDATE
        estoque = Produto.objects.filter(id=falta.produto.id).values_list("estoque", flat=True).first()
        if estoque is None:
            messages.error(request, "Este produto não está mais disponível.")
            return redirect("loja:produtos")
        devolver_token_pedido(request, token)  # pode corrigir a quantidade e reenviar
        nome = falta.produto.nome
        if pelo_checkout:
            messages.error(request, f"“{nome}” esgotou. Tire da sacola para continuar." if estoque == 0 else
                           f"Só restam {estoque} unidade(s) de “{nome}”. Ajuste a quantidade na sacola.")
        else:
            messages.error(request, "Produto esgotado." if estoque == 0 else
                           f"Só restam {estoque} unidade(s) de “{nome}”.")
        return volta

    if pelo_checkout:
        request.session.pop(SESSAO_SACOLA, None)
        request.session[SESSAO_ANIMAR] = novo.id
        if visitante:
            return redirect("loja:pedido_acompanhar", codigo=novo.codigo)
        return redirect("loja:pedido_confirmado", id=novo.id)
    produto, tamanho, quantidade = itens[0]
    total = f"{precos[produto.id] * quantidade:.2f}".replace(".", ",")
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

    def get_default_redirect_url(self):
        # sem "next": a equipe vai direto para o painel; cliente continua indo para a loja
        if self.request.user.is_staff:
            return reverse("loja:painel_inicio")
        return super().get_default_redirect_url()


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
    return render(request, "conta.html", {"pedidos": PEDIDOS.filter(usuario=request.user)})


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


def dias_escolhidos(request):
    return int(request.GET["dias"]) if request.GET.get("dias") in {str(p) for p in PERIODOS} else 30


@somente_staff
def painel_inicio(request):
    dias = dias_escolhidos(request)
    return render(request, "painel/inicio.html",
                  resumo(dias) | {"dias": dias, "periodos": PERIODOS, "sugestoes": SUGESTOES})


@somente_staff
def painel_financas(request):
    dias = dias_escolhidos(request)
    return render(request, "painel/financas.html", financas(dias) | {"dias": dias, "periodos": PERIODOS})


@somente_staff
def painel_clientes(request):
    return render(request, "painel/clientes.html", {
        "ranking": ranking_clientes(),
        "total_clientes": User.objects.filter(groups__name=CLIENTES).count(),
        "equipe": User.objects.filter(groups__name=FUNCIONARIOS).order_by("username"),
    })


@somente_staff
@require_POST
def painel_estoque_repor(request, id):
    """Entrada de mercadoria: soma unidades ao estoque (UPDATE com F(): duas entradas juntas não se perdem)."""
    produto = get_object_or_404(Produto, id=id)
    quantidade = request.POST.get("quantidade", "").strip()
    if not inteiro_ascii(quantidade) or not 1 <= int(quantidade) <= 999:
        messages.error(request, "Informe de 1 a 999 unidades para repor.")
    else:
        Produto.objects.filter(id=produto.id).update(estoque=F("estoque") + int(quantidade))
        produto.refresh_from_db(fields=["estoque"])
        messages.success(request, f"Entrada de {quantidade} unidade(s) em “{produto.nome}”. Estoque agora: {produto.estoque}.")
    return redirect(f"{reverse('loja:painel_produtos')}#produto-{produto.id}")


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
                  {"produtos": filtrar(busca, categoria), "busca": busca, "categoria": categoria} | estoque())


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
    except ProtectedError:  # ItemPedido.produto é PROTECT
        total = Pedido.objects.filter(itens__produto=produto).distinct().count()
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
    # JOIN pedidos + usuário; itens, produtos e categorias em mais 3 consultas
    return render(request, "painel/pedidos.html",
                  # .all(): cópia nova a cada acesso (o PEDIDOS do módulo não guarda resultado entre requisições)
                  {"pedidos": PEDIDOS.all(), "entregas": entregas(PEDIDOS[:12]), "cd": CD})