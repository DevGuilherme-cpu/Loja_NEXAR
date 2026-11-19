import unicodedata

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
    imagem_2 = models.ImageField(upload_to="produtos/", blank=True)
    # .glb enviado pelo painel ou link
    modelo_3d = models.FileField(upload_to="modelos/", blank=True, max_length=255)
    cor = models.CharField(max_length=7, blank=True, help_text="Cor da peça 3D, ex.: #1F2F6B")
    # PROTECT: não apaga categoria com produtos
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)

    class Meta:
        db_table = "produtos"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(preco__gte=0), name="produto_preco_nao_negativo"),
        ]

    def __str__(self):
        return self.nome

    @property
    def grade(self):
        """Tipo de numeração: roupa e calca (P a GG), tenis (38 a 44) ou unico (boné, óculos...)."""
        # shortcut: deduzido do nome e da categoria; se aparecerem exceções, virar um campo no Produto
        texto = unicodedata.normalize("NFKD", f"{self.nome} {self.categoria.nome}").encode("ascii", "ignore")
        texto = texto.decode().lower()
        if "tenis" in texto or "calcado" in texto:
            return "tenis"
        if "calca" in texto or "bermuda" in texto:
            return "calca"
        if any(p in texto for p in ("bone", "oculos", "acessorio", "bolsa", "meia")):
            return "unico"
        return "roupa"

    @property
    def tamanhos(self):
        return GRADES[self.grade]


ROUPA = ["P", "M", "G", "GG"]
GRADES = {"roupa": ROUPA, "calca": ROUPA, "tenis": [str(n) for n in range(38, 45)], "unico": ["U"]}


class Pedido(models.Model):
    TAMANHOS = [(t, t) for t in ROUPA] + [(t, t) for t in GRADES["tenis"]] + [("U", "Único")]

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

    # entrega e pagamento (checkout). Vazios em pedidos antigos e nos feitos pelo painel/admin.
    ENVIOS = [("padrao", "Padrão"), ("expresso", "Expresso")]
    PAGAMENTOS = [("pix", "Pix"), ("cartao", "Cartão"), ("boleto", "Boleto")]
    entrega_nome = models.CharField("nome de quem recebe", max_length=100, blank=True)
    # só os 2 últimos dígitos (***.***.***-12): o CPF completo é conferido e não é guardado
    entrega_cpf = models.CharField("CPF (mascarado)", max_length=14, blank=True)
    entrega_telefone = models.CharField("telefone", max_length=15, blank=True)
    entrega_cep = models.CharField("CEP", max_length=9, blank=True)
    entrega_endereco = models.CharField("endereço", max_length=200, blank=True)
    entrega_bairro = models.CharField("bairro", max_length=60, blank=True)
    entrega_cidade = models.CharField("cidade", max_length=60, blank=True)
    entrega_uf = models.CharField("UF", max_length=2, blank=True)
    envio = models.CharField(max_length=10, choices=ENVIOS, blank=True)
    pagamento = models.CharField(max_length=10, choices=PAGAMENTOS, blank=True)
    frete = models.DecimalField(max_digits=8, decimal_places=2, default=0, validators=[MinValueValidator(0)])

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

    @property
    def total_com_frete(self):
        return None if self.total is None else self.total + self.frete
