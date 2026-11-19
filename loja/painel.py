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
        lista.append({"id": p.id, "cliente": p.cliente,
                      "produto": f"{p.quantidade}× {p.produto.nome}", "total": reais(valor(p)),
                      "cidade": cidade, "uf": uf, "lon": lon, "lat": lat})
    return lista


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
        # ordem fixa (P, M, G, GG, 38...44, Único), só os tamanhos que venderam
        "tamanhos": [{"nome": rotulo, "texto": pecas(tamanhos[nome]),
                      "pct": round(tamanhos[nome] / (max(tamanhos.values(), default=0) or 1) * 100)}
                     for nome, rotulo in Pedido.TAMANHOS if tamanhos[nome]],
        "estoque_baixo": Produto.objects.filter(estoque__lte=ESTOQUE_BAIXO).order_by("estoque", "nome")[:6],
        "ultimos": Pedido.objects.select_related("usuario", "produto")[:5],
    }
