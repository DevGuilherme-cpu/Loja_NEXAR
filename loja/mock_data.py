# Dados de exemplo (usados pelo comando popular_loja)

from datetime import datetime
from types import SimpleNamespace

SAPATO_3D = "/static/modelos/tenis.glb"  # Shopify, CC BY 4.0
OCULOS_3D = "/static/modelos/oculos.glb"  # Khronos Group, CC BY 4.0

# cor de cada peça no 3D
CORES = {
    "Camiseta Box Logo": "#E8641E", "Camiseta Grid": "#F2F2EF", "Moletom Heavy": "#22306B",
    "Moletom Drop 01": "#EDEDE9", "Calça Cargo Tech": "#5B6542", "Calça Wide Denim": "#8FB3D9",
    "Boné 6-Panel": "#F4F4F1",
}

CATEGORIAS = [
    {"id": 1, "nome": "Camisetas"},
    {"id": 2, "nome": "Moletons"},
    {"id": 3, "nome": "Calças"},
    {"id": 4, "nome": "Bonés"},
    {"id": 5, "nome": "Acessórios"},
]


def _foto(nome):
    return SimpleNamespace(url=f"/static/img/produtos/{nome}.jpg")


# foto: nome-1.jpg e nome-2.jpg em static/img/produtos
def _p(id, nome, preco, cat_id, descricao, modelo_3d=None, estoque=12, foto=None):
    cat = next(c for c in CATEGORIAS if c["id"] == cat_id)
    return {"id": id, "nome": nome, "descricao": descricao, "preco": preco, "estoque": estoque,
            "imagem": _foto(f"{foto}-1") if foto else None,
            "imagem_2": _foto(f"{foto}-2") if foto else None,
            "modelo_3d": modelo_3d, "categoria_id": cat_id, "categoria": cat["nome"]}


# fotos do Pexels (IDs nos comentários)
PRODUTOS = [
    _p(1, "Camiseta Box Logo", 149.90, 1, "Algodão 240g, modelagem boxy, logo NEXAR bordado no peito.", foto="camiseta-box"),  # 36392069 / 18814063
    _p(2, "Camiseta Grid", 159.90, 1, "Estampa grid em silk, gola canelada reforçada.", foto="camiseta-grid"),  # 11671964 / 17858294
    _p(3, "Moletom Heavy", 399.90, 2, "Moletom 480g peluciado, ombro caído, punho largo.", foto="moletom-heavy"),  # 30095407 / 30095401
    _p(4, "Moletom Drop 01", 429.90, 2, "Edição limitada do primeiro drop. Bordado 3D nas costas.", estoque=3, foto="moletom-drop"),  # 8217312 / 8217415
    _p(5, "Calça Cargo Tech", 349.90, 3, "Ripstop com seis bolsos e barra ajustável.", foto="calca-cargo"),  # 11716436 / 19220710
    _p(6, "Calça Wide Denim", 389.90, 3, "Jeans 14oz, corte wide, lavagem escura.", foto="calca-wide"),  # 17720437 / 31703299
    _p(7, "Boné 6-Panel", 129.90, 4, "Sarja de algodão, aba curva, fecho de metal.", foto="bone"),  # 9558763 / 9558254
    _p(8, "Tênis Runner X", 699.90, 5, "Cabedal em mesh e camurça, solado de borracha.", SAPATO_3D, foto="tenis"),  # 7193623 / 27008322
    _p(9, "Óculos Nexar Shade", 259.90, 5, "Armação acetato, lente com proteção UV400.", OCULOS_3D, foto="oculos"),  # 27353350 / 8217769
]

PEDIDOS = [
    {"id": 5, "data": datetime(2026, 11, 5, 18, 40), "cliente": "eva.costa", "produto": "Tênis Runner X", "categoria": "Acessórios", "tamanho": "G", "quantidade": 1, "total": 699.90},
    {"id": 4, "data": datetime(2026, 11, 4, 9, 15), "cliente": "daniel", "produto": "Boné 6-Panel", "categoria": "Bonés", "tamanho": "M", "quantidade": 2, "total": 259.80},
    {"id": 3, "data": datetime(2026, 11, 3, 21, 2), "cliente": "carla.m", "produto": "Calça Cargo Tech", "categoria": "Calças", "tamanho": "P", "quantidade": 1, "total": 349.90},
    {"id": 2, "data": datetime(2026, 11, 2, 14, 10), "cliente": "bruno", "produto": "Moletom Heavy", "categoria": "Moletons", "tamanho": "GG", "quantidade": 1, "total": 399.90},
    {"id": 1, "data": datetime(2026, 11, 1, 11, 30), "cliente": "ana.souza", "produto": "Camiseta Box Logo", "categoria": "Camisetas", "tamanho": "M", "quantidade": 3, "total": 449.70},
]