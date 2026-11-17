from django.conf import settings
from django.core.validators import MinValueValidator
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
    preco = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
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
        constraints = [
            models.CheckConstraint(condition=models.Q(preco__gte=0), name="produto_preco_nao_negativo"),
        ]

    def __str__(self):
        return self.nome


class Pedido(models.Model):
    TAMANHOS = [("P", "P"), ("M", "M"), ("G", "G"), ("GG", "GG")]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT)
    tamanho = models.CharField(max_length=2, choices=TAMANHOS)
    quantidade = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    # preço do produto no momento da compra: se o preço do produto mudar depois,
    # o total dos pedidos antigos continua o mesmo
    # blank=True: no admin pode ficar vazio e o save() copia o preço atual do produto
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2, blank=True,
                                         validators=[MinValueValidator(0)])
    data = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pedidos"
        ordering = ["-data"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantidade__gte=1), name="pedido_quantidade_minima_1"),
            models.CheckConstraint(condition=models.Q(preco_unitario__gte=0), name="pedido_preco_unitario_nao_negativo"),
        ]

    def __str__(self):
        return f"Pedido {self.id} - {self.usuario} - {self.produto}"

    def save(self, *args, **kwargs):
        # Sem preço informado (ex.: pedido criado pelo /admin/), grava o preço do produto agora
        if self.preco_unitario is None and self.produto_id:
            self.preco_unitario = self.produto.preco
        super().save(*args, **kwargs)

    @property
    def total(self):
        if self.preco_unitario is None:
            return None
        return self.preco_unitario * self.quantidade
