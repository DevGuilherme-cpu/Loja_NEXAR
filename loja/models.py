from django.conf import settings
from django.db import models


class Categoria(models.Model):
    nome = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "categorias"
        ordering = ["id"]

    def __str__(self):
        return self.nome


class Produto(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    estoque = models.PositiveIntegerField(default=0)
    imagem = models.ImageField(upload_to="produtos/", blank=True)
    imagem_2 = models.ImageField(upload_to="produtos/", blank=True)  # aparece no hover do card
    # .glb enviado pelo painel, ou um link https:// direto para o modelo
    modelo_3d = models.FileField(upload_to="modelos/", blank=True, max_length=255)
    # PROTECT: não deixa apagar categoria que ainda tem produto (o MySQL também barraria pela FK)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)

    class Meta:
        db_table = "produtos"
        ordering = ["id"]

    def __str__(self):
        return self.nome


class Pedido(models.Model):
    TAMANHOS = [("P", "P"), ("M", "M"), ("G", "G"), ("GG", "GG")]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT)
    tamanho = models.CharField(max_length=2, choices=TAMANHOS)
    quantidade = models.PositiveIntegerField(default=1)
    data = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pedidos"
        ordering = ["-data"]

    def __str__(self):
        return f"Pedido {self.id} - {self.usuario} - {self.produto}"

    @property
    def total(self):
        return self.produto.preco * self.quantidade
