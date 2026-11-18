"""Números da visão geral do painel.

As contas são feitas em Python sobre os pedidos do período, e não com TruncDate no banco:
no MySQL o TruncDate com fuso horário depende de tabelas que quase nunca estão instaladas.
"""
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.utils import timezone

from .models import Pedido, Produto

PERIODOS = (7, 30, 90)
ESTOQUE_BAIXO = 5


def reais(valor):
    """1234.5 -> "R$ 1.234,50" """
    return "R$ " + f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def inicio_do_dia(dia):
    return timezone.make_aware(datetime.combine(dia, time.min))


def pedidos_entre(inicio=None, fim=None):
    # shortcut: traz os pedidos do período para a memória; com milhares de pedidos, trocar por aggregate no banco
    qs = Pedido.objects.select_related("usuario", "produto__categoria")
    if inicio:
        qs = qs.filter(data__gte=inicio)
    if fim:
        qs = qs.filter(data__lt=fim)
    return list(qs)


def valor(pedido):
    return (pedido.preco_unitario or Decimal(0)) * pedido.quantidade


def totais(pedidos):
    faturamento = sum((valor(p) for p in pedidos), Decimal(0))
    n = len(pedidos)
    return {"faturamento": faturamento, "pedidos": n, "pecas": sum(p.quantidade for p in pedidos),
            "ticket": faturamento / n if n else Decimal(0)}


def variacao(atual, anterior):
    """Variação em % em relação ao período anterior (None quando não há base para comparar)."""
    return round((atual - anterior) / anterior * 100) if anterior else None


def barras(contagem, formato=str, limite=None):
    """{nome: número} -> lista para o gráfico de barras, da maior para a menor."""
    itens = sorted(contagem.items(), key=lambda i: i[1], reverse=True)[:limite]
    maior = max((v for _, v in itens), default=0) or 1
    return [{"nome": nome, "texto": formato(v), "pct": round(v / maior * 100)} for nome, v in itens]


def resumo(dias=30):
    hoje = timezone.localdate()
    inicio = inicio_do_dia(hoje - timedelta(days=dias - 1))
    atuais = pedidos_entre(inicio)
    t = totais(atuais)
    ant = totais(pedidos_entre(inicio - timedelta(days=dias), inicio))

    kpis = [
        {"nome": "Faturamento", "valor": reais(t["faturamento"]), "var": variacao(t["faturamento"], ant["faturamento"])},
        {"nome": "Pedidos", "valor": t["pedidos"], "var": variacao(t["pedidos"], ant["pedidos"])},
        {"nome": "Ticket médio", "valor": reais(t["ticket"]), "var": variacao(t["ticket"], ant["ticket"])},
        {"nome": "Peças vendidas", "valor": t["pecas"], "var": variacao(t["pecas"], ant["pecas"])},
    ]

    por_dia, pedidos_dia = defaultdict(Decimal), Counter()
    categorias, produtos, tamanhos = defaultdict(Decimal), Counter(), Counter()
    for p in atuais:
        dia = timezone.localdate(p.data)
        por_dia[dia] += valor(p)
        pedidos_dia[dia] += 1
        categorias[p.produto.categoria.nome] += valor(p)
        produtos[p.produto.nome] += p.quantidade
        tamanhos[p.tamanho] += p.quantidade

    dias_lista = [hoje - timedelta(days=i) for i in range(dias - 1, -1, -1)]
    serie = [{"data": d.strftime("%d/%m"), "valor": float(por_dia[d]), "texto": reais(por_dia[d]),
              "pedidos": pedidos_dia[d]} for d in dias_lista]
    melhor = max(serie, key=lambda s: s["valor"])

    def pecas(n):
        return f"{n} peça{'s' if n != 1 else ''}"

    return {
        "kpis": kpis,
        "faturamento_periodo": reais(t["faturamento"]),
        "serie": serie,
        "melhor_dia": melhor if melhor["valor"] else None,
        "categorias": barras(categorias, reais),
        "mais_vendidos": barras(produtos, pecas, limite=5),
        # ordem fixa P, M, G, GG (não por quantidade)
        "tamanhos": [{"nome": nome, "texto": pecas(tamanhos[nome]),
                      "pct": round(tamanhos[nome] / (max(tamanhos.values(), default=0) or 1) * 100)}
                     for nome, _ in Pedido.TAMANHOS],
        "estoque_baixo": Produto.objects.filter(estoque__lte=ESTOQUE_BAIXO).order_by("estoque", "nome")[:6],
        "ultimos": Pedido.objects.select_related("usuario", "produto")[:5],
    }
