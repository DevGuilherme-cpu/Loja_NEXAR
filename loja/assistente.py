"""Assistente do painel: responde perguntas sobre a loja consultando o banco."""
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from .models import Pedido, Produto
from .painel import ESTOQUE_BAIXO, inicio_do_dia, pedidos_entre, reais, totais, valor

SUGESTOES = [
    "Quanto vendi esta semana?",
    "O que está acabando no estoque?",
    "Qual o produto mais vendido?",
    "Qual categoria vende mais?",
]

AJUDA = ("Posso responder sobre faturamento, pedidos, ticket médio, produtos mais e menos vendidos, "
         "categorias, tamanhos, clientes e estoque. Diga também o período: hoje, ontem, esta semana, "
         "este mês, este ano ou \"últimos 15 dias\".")


def normalizar(texto):
    """minúsculas e sem acento: "Está acabando?" -> "esta acabando?" """
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def periodo(t):
    """(início, fim, descrição) a partir das palavras da pergunta. Sem período = desde o início."""
    hoje = timezone.localdate()
    if "hoje" in t:
        return inicio_do_dia(hoje), None, "hoje"
    if "ontem" in t:
        return inicio_do_dia(hoje - timedelta(days=1)), inicio_do_dia(hoje), "ontem"
    if m := re.search(r"(\d{1,3}) dias", t):
        n = max(int(m.group(1)), 1)
        return inicio_do_dia(hoje - timedelta(days=n - 1)), None, f"nos últimos {n} dias"
    if "semana" in t:
        return inicio_do_dia(hoje - timedelta(days=6)), None, "nos últimos 7 dias"
    if re.search(r"\bmes\b", t):
        return inicio_do_dia(hoje - timedelta(days=29)), None, "nos últimos 30 dias"
    if re.search(r"\bano\b", t):
        return inicio_do_dia(hoje - timedelta(days=364)), None, "nos últimos 12 meses"
    return None, None, "desde o início"


def plural(n, palavra):
    return f"{n} {palavra}{'' if n == 1 else 's'}"


def responder(pergunta):
    t = normalizar(pergunta.strip())
    if not t or re.search(r"\b(ajuda|oi|ola|bom dia|boa tarde|boa noite)\b|o que voce", t):
        return "Olá! " + AJUDA

    inicio, fim, quando = periodo(t)
    pedidos = pedidos_entre(inicio, fim)

    # produto citado pelo nome: "como está o moletom heavy?"
    for produto in Produto.objects.all():
        if normalizar(produto.nome) in t:
            dele = [p for p in pedidos if p.produto_id == produto.id]
            soma = totais(dele)
            return (f"{produto.nome}: {plural(soma['pecas'], 'peça')} vendida{'' if soma['pecas'] == 1 else 's'} "
                    f"{quando} ({reais(soma['faturamento'])}). Estoque atual: {produto.estoque}.")

    if re.search(r"estoque|acaband|repor|esgot|falt", t):
        baixos = Produto.objects.filter(estoque__lte=ESTOQUE_BAIXO).order_by("estoque", "nome")
        if not baixos:
            return f"Nenhum produto com {ESTOQUE_BAIXO} unidades ou menos. O estoque está tranquilo."
        linhas = [f"• {p.nome}: {'esgotado' if p.estoque == 0 else plural(p.estoque, 'unidade')}" for p in baixos]
        return f"Precisam de reposição ({ESTOQUE_BAIXO} unidades ou menos):\n" + "\n".join(linhas)

    if re.search(r"menos vend|parad|encalh|sem venda|nao vend", t):
        vendidos = {p.produto_id for p in pedidos}
        parados = [p.nome for p in Produto.objects.order_by("nome") if p.id not in vendidos]
        if not parados:
            return f"Todos os produtos tiveram venda {quando}."
        return f"Sem nenhuma venda {quando}: " + ", ".join(parados) + "."

    if not pedidos:
        return f"Não houve pedidos {quando}, então ainda não tenho números para mostrar."

    # categoria e tamanho antes de "mais vendido": "tamanho mais vendido" é pergunta de tamanho
    if "categori" in t:
        soma = defaultdict(Decimal)
        for p in pedidos:
            soma[p.produto.categoria.nome] += valor(p)
        ordem = sorted(soma.items(), key=lambda i: i[1], reverse=True)
        linhas = [f"• {nome}: {reais(v)}" for nome, v in ordem]
        return f"A categoria que mais vende {quando} é {ordem[0][0]}.\n" + "\n".join(linhas)

    if "tamanh" in t:
        contagem = Counter()
        for p in pedidos:
            contagem[p.tamanho] += p.quantidade
        linhas = [f"• {rotulo}: {plural(contagem[nome], 'peça')}" for nome, rotulo in Pedido.TAMANHOS if contagem[nome]]
        return f"O tamanho mais pedido {quando} é {contagem.most_common(1)[0][0]}.\n" + "\n".join(linhas)

    if re.search(r"mais vend|top|campe|melhor|sucesso|ranking", t):
        contagem = Counter()
        for p in pedidos:
            contagem[p.produto.nome] += p.quantidade
        linhas = [f"{i}. {nome}: {plural(n, 'peça')}" for i, (nome, n) in enumerate(contagem.most_common(3), 1)]
        return f"Mais vendidos {quando}:\n" + "\n".join(linhas)

    soma = totais(pedidos)
    if re.search(r"ticket|media|medio", t):
        return f"O ticket médio {quando} é {reais(soma['ticket'])} ({plural(soma['pedidos'], 'pedido')})."

    if re.search(r"client|comprador|quem compr", t):
        por_cliente = defaultdict(Decimal)
        for p in pedidos:
            por_cliente[p.cliente] += valor(p)
        nome, v = max(por_cliente.items(), key=lambda i: i[1])
        return (f"O cliente que mais comprou {quando} foi {nome}, com {reais(v)}. "
                f"Clientes com pedido {quando}: {len(por_cliente)}.")

    if "pedido" in t:
        ultimo = max(pedidos, key=lambda p: p.data)
        return (f"Foram {plural(soma['pedidos'], 'pedido')} {quando}. O último foi o #{ultimo.id}, "
                f"de {ultimo.cliente}: {ultimo.quantidade}× {ultimo.produto.nome}.")

    if re.search(r"fatur|vend|receit|ganh|dinheiro|quanto|lucr", t):
        return (f"Você faturou {reais(soma['faturamento'])} {quando}, em {plural(soma['pedidos'], 'pedido')} "
                f"e {plural(soma['pecas'], 'peça')}.")

    return "Ainda não sei responder isso. " + AJUDA
