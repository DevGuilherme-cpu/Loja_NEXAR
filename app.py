from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# shortcut: dados falsos do mock_data.py; Eliton troca por consultas MySQL quando o banco estiver pronto
from loja.mock_data import CATEGORIAS, PRODUTOS

app = FastAPI(title="NEXAR")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"destaques": PRODUTOS[:4], "categorias": CATEGORIAS})


@app.get("/produtos")
def produtos(request: Request, busca: str = "", categoria: str = ""):
    lista = [p for p in PRODUTOS
             if busca.lower() in p["nome"].lower() and (not categoria or str(p["categoria_id"]) == categoria)]
    return templates.TemplateResponse(request, "produtos.html", {
        "produtos": lista, "categorias": CATEGORIAS, "busca": busca, "categoria": categoria})


@app.get("/produto/{id}")
def produto(request: Request, id: int):
    p = next((p for p in PRODUTOS if p["id"] == id), None)
    if not p:
        raise HTTPException(404, "Produto não encontrado")
    return templates.TemplateResponse(request, "produto.html", {"produto": p})


@app.get("/login")
def login(request: Request):
    return templates.TemplateResponse(request, "login.html", {"erro": None})


@app.get("/cadastro")
def cadastro(request: Request):
    return templates.TemplateResponse(request, "cadastro.html", {"erro": None})