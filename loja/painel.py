"""Números da visão geral do painel.

As contas são feitas em Python sobre os pedidos do período, e não com TruncDate no banco:
no MySQL o TruncDate com fuso horário depende de tabelas que quase nunca estão instaladas.
"""
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.utils import timezone

from .models import ItemPedido, Pedido, Produto

PERIODOS = (7, 30, 90)
ESTOQUE_BAIXO = 5


def reais(valor):
    """1234.5 -> "R$ 1.234,50" """
    return "R$ " + f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def inicio_do_dia(dia):
    return timezone.make_aware(datetime.combine(dia, time.min))


def itens_entre(inicio=None, fim=None):
    """Peças vendidas no período (cada uma com o pedido dela: data e cliente em item.pedido)."""
    # shortcut: traz as peças do período para a memória; com milhares de pedidos, trocar por aggregate no banco
    qs = ItemPedido.objects.select_related("pedido__usuario", "produto__categoria")
    if inicio:
        qs = qs.filter(pedido__data__gte=inicio)
    if fim:
        qs = qs.filter(pedido__data__lt=fim)
    return list(qs)


def valor(item):
    return item.total


def totais(itens):
    faturamento = sum((valor(i) for i in itens), Decimal(0))
    n = len({i.pedido_id for i in itens})
    return {"faturamento": faturamento, "pedidos": n, "pecas": sum(i.quantidade for i in itens),
            "ticket": faturamento / n if n else Decimal(0)}


def variacao(atual, anterior):
    """Variação em % em relação ao período anterior (None quando não há base para comparar)."""
    return round((atual - anterior) / anterior * 100) if anterior else None


def barras(contagem, formato=str, limite=None):
    """{nome: número} -> lista para o gráfico de barras, da maior para a menor."""
    itens = sorted(contagem.items(), key=lambda i: i[1], reverse=True)[:limite]
    maior = max((v for _, v in itens), default=0) or 1
    return [{"nome": nome, "texto": formato(v), "pct": round(v / maior * 100)} for nome, v in itens]


# Mapa de entregas (simulação): o Pedido não tem endereço, então cada pedido recebe uma capital
# fixa pelo número dele e sai do centro de distribuição em São Paulo.
CD = {"cidade": "São Paulo", "uf": "SP", "lon": -46.63, "lat": -23.55}
CIDADES = [
    ("Rio de Janeiro", "RJ", -43.20, -22.91), ("Belo Horizonte", "MG", -43.94, -19.92),
    ("Vitória", "ES", -40.31, -20.32), ("Curitiba", "PR", -49.27, -25.43),
    ("Florianópolis", "SC", -48.55, -27.60), ("Porto Alegre", "RS", -51.23, -30.03),
    ("Brasília", "DF", -47.88, -15.79), ("Goiânia", "GO", -49.25, -16.68),
    ("Campo Grande", "MS", -54.62, -20.47), ("Cuiabá", "MT", -56.10, -15.60),
    ("Salvador", "BA", -38.50, -12.97), ("Aracaju", "SE", -37.07, -10.91),
    ("Maceió", "AL", -35.73, -9.67), ("Recife", "PE", -34.88, -8.05),
    ("João Pessoa", "PB", -34.86, -7.12), ("Natal", "RN", -35.21, -5.79),
    ("Fortaleza", "CE", -38.54, -3.72), ("Teresina", "PI", -42.80, -5.09),
    ("São Luís", "MA", -44.30, -2.53), ("Belém", "PA", -48.50, -1.46),
    ("Macapá", "AP", -51.07, 0.03), ("Manaus", "AM", -60.02, -3.12),
    ("Boa Vista", "RR", -60.67, 2.82), ("Porto Velho", "RO", -63.90, -8.76),
    ("Rio Branco", "AC", -67.81, -9.97), ("Palmas", "TO", -48.33, -10.18),
]


def entregas(pedidos):
    lista = []
    por_uf = {c[1]: c for c in CIDADES} | {CD["uf"]: (CD["cidade"], CD["uf"], CD["lon"], CD["lat"])}
    for p in pedidos:
        cidade, uf, lon, lat = CIDADES[(p.id * 7) % len(CIDADES)]
        if p.entrega_uf in por_uf:
            # pedido do checkout: o ponto do mapa é a capital do estado; o nome é a cidade de verdade
            _, uf, lon, lat = por_uf[p.entrega_uf]
            cidade = p.entrega_cidade
        itens = list(p.itens.all())
        primeiro = f"{itens[0].quantidade}× {itens[0].produto.nome}" if itens else "Sem peças"
        lista.append({"id": p.id, "cliente": p.cliente,
                      "produto": primeiro + (f" + {len(itens) - 1} peça(s)" if len(itens) > 1 else ""),
                      "total": reais(p.total), "cidade": cidade, "uf": uf, "lon": lon, "lat": lat})
    return lista


def resumo(dias=30):
    hoje = timezone.localdate()
    inicio = inicio_do_dia(hoje - timedelta(days=dias - 1))
    atuais = itens_entre(inicio)
    t = totais(atuais)
    ant = totais(itens_entre(inicio - timedelta(days=dias), inicio))

    kpis = [
        {"nome": "Faturamento", "valor": reais(t["faturamento"]), "var": variacao(t["faturamento"], ant["faturamento"])},
        {"nome": "Pedidos", "valor": t["pedidos"], "var": variacao(t["pedidos"], ant["pedidos"])},
        {"nome": "Ticket médio", "valor": reais(t["ticket"]), "var": variacao(t["ticket"], ant["ticket"])},
        {"nome": "Peças vendidas", "valor": t["pecas"], "var": variacao(t["pecas"], ant["pecas"])},
    ]

    por_dia, pedidos_dia = defaultdict(Decimal), defaultdict(set)
    categorias, produtos, tamanhos = defaultdict(Decimal), Counter(), Counter()
    for i in atuais:
        dia = timezone.localdate(i.pedido.data)
        por_dia[dia] += valor(i)
        pedidos_dia[dia].add(i.pedido_id)
        categorias[i.produto.categoria.nome] += valor(i)
        produtos[i.produto.nome] += i.quantidade
        tamanhos[i.tamanho] += i.quantidade

    dias_lista = [hoje - timedelta(days=i) for i in range(dias - 1, -1, -1)]
    serie = [{"data": d.strftime("%d/%m"), "valor": float(por_dia[d]), "texto": reais(por_dia[d]),
              "pedidos": len(pedidos_dia[d])} for d in dias_lista]
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
        # ordem fixa (P, M, G, GG, 38...44, Único), só os tamanhos que venderam
        "tamanhos": [{"nome": rotulo, "texto": pecas(tamanhos[nome]),
                      "pct": round(tamanhos[nome] / (max(tamanhos.values(), default=0) or 1) * 100)}
                     for nome, rotulo in Pedido.TAMANHOS if tamanhos[nome]],
        "estoque_baixo": Produto.objects.filter(estoque__lte=ESTOQUE_BAIXO).order_by("estoque", "nome")[:6],
        "ultimos": Pedido.objects.select_related("usuario").prefetch_related("itens__produto")[:5],
    }


def pedidos_de(inicio=None, fim=None):
    """Pedidos do período, com as peças (para total e frete de cada compra)."""
    qs = Pedido.objects.select_related("usuario").prefetch_related("itens")
    if inicio:
        qs = qs.filter(data__gte=inicio)
    if fim:
        qs = qs.filter(data__lt=fim)
    return list(qs)


MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def financas(dias=30):
    """Página Finanças: quanto entrou (peças + frete), por forma de pagamento e mês a mês."""
    hoje = timezone.localdate()
    inicio = inicio_do_dia(hoje - timedelta(days=dias - 1))

    def somar(pedidos):
        pecas = sum((p.total for p in pedidos), Decimal(0))
        fretes = sum((p.frete for p in pedidos), Decimal(0))
        n = len(pedidos)
        return {"pecas": pecas, "fretes": fretes, "total": pecas + fretes, "n": n,
                "ticket": (pecas + fretes) / n if n else Decimal(0)}

    atuais = pedidos_de(inicio)
    t, ant = somar(atuais), somar(pedidos_de(inicio - timedelta(days=dias), inicio))
    kpis = [
        {"nome": "Total recebido", "valor": reais(t["total"]), "var": variacao(t["total"], ant["total"])},
        {"nome": "Venda de peças", "valor": reais(t["pecas"]), "var": variacao(t["pecas"], ant["pecas"])},
        {"nome": "Fretes cobrados", "valor": reais(t["fretes"]), "var": variacao(t["fretes"], ant["fretes"])},
        {"nome": "Ticket médio", "valor": reais(t["ticket"]), "var": variacao(t["ticket"], ant["ticket"])},
    ]

    rotulos = dict(Pedido.PAGAMENTOS)
    por_pagamento, por_envio = defaultdict(Decimal), defaultdict(Decimal)
    for p in atuais:
        # pedidos sem checkout (painel, simulação, dados de exemplo) não têm forma de pagamento
        por_pagamento[rotulos.get(p.pagamento, "Sem checkout")] += p.total_com_frete
        por_envio[dict(Pedido.ENVIOS).get(p.envio, "Sem checkout")] += p.total_com_frete

    # últimos 6 meses, do mais antigo para o atual
    meses = []
    ano, mes = hoje.year, hoje.month
    for _ in range(6):
        meses.insert(0, (ano, mes))
        ano, mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    por_mes = defaultdict(lambda: {"total": Decimal(0), "n": 0})
    for p in pedidos_de(inicio_do_dia(hoje.replace(year=meses[0][0], month=meses[0][1], day=1))):
        data = timezone.localdate(p.data)
        por_mes[(data.year, data.month)]["total"] += p.total_com_frete
        por_mes[(data.year, data.month)]["n"] += 1
    maior = max((por_mes[m]["total"] for m in meses), default=0) or 1
    mensal = [{"nome": f"{MESES[m - 1]}/{a % 100:02d}", "pedidos": por_mes[(a, m)]["n"],
               "texto": reais(por_mes[(a, m)]["total"]), "pct": round(por_mes[(a, m)]["total"] / maior * 100)}
              for a, m in meses]

    return {"kpis": kpis, "total_periodo": reais(t["total"]), "pedidos_periodo": t["n"],
            "por_pagamento": barras(por_pagamento, reais), "por_envio": barras(por_envio, reais), "mensal": mensal}


def estoque():
    """Resumo da página Estoque: peças guardadas, quanto valem a preço de venda e o que precisa repor."""
    produtos = list(Produto.objects.all())
    return {
        "estoque_pecas": sum(p.estoque for p in produtos),
        "estoque_valor": reais(sum((p.preco * p.estoque for p in produtos), Decimal(0))),
        "estoque_esgotados": sum(1 for p in produtos if p.estoque == 0),
        "estoque_baixo": sum(1 for p in produtos if 0 < p.estoque <= ESTOQUE_BAIXO),
        "estoque_limite": ESTOQUE_BAIXO,
    }


def ranking_clientes():
    """Quem mais compra, do maior gasto para o menor. Visitante (sem conta) conta pelo e-mail."""
    # shortcut: soma em Python todos os pedidos; com milhares de pedidos, trocar por aggregate no banco
    clientes = {}
    for p in Pedido.objects.select_related("usuario").prefetch_related("itens").order_by("data"):
        chave = ("conta", p.usuario_id) if p.usuario_id else ("visitante", p.entrega_email or p.entrega_nome)
        c = clientes.setdefault(chave, {"nome": p.cliente, "conta": bool(p.usuario_id),
                                        "equipe": bool(p.usuario_id and p.usuario.is_staff),
                                        "pedidos": 0, "pecas": 0, "total": Decimal(0)})
        c["pedidos"] += 1
        c["pecas"] += p.quantidade
        c["total"] += p.total_com_frete
        c["ultimo"] = p.data  # order_by("data"): o último que passar é o mais recente
    lista = sorted(clientes.values(), key=lambda c: c["total"], reverse=True)
    for posicao, c in enumerate(lista, 1):
        c["posicao"], c["texto"] = posicao, reais(c["total"])
    return lista
