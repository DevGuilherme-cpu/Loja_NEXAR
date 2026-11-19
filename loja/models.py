import secrets
import unicodedata
from decimal import Decimal

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


TAMANHOS = [(t, t) for t in ROUPA] + [(t, t) for t in GRADES["tenis"]] + [("U", "Único")]


class Pedido(models.Model):
    """A compra: quem comprou, entrega, frete e pagamento. As peças ficam em ItemPedido (pedido.itens)."""
    TAMANHOS = TAMANHOS

    # vazio = compra de visitante (sem conta): os dados ficam em entrega_* e entrega_email
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
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
    entrega_email = models.EmailField("e-mail", blank=True)
    # código secreto do link de acompanhamento (/pedido/acompanhar/<codigo>/): quem não tem conta
    # acompanha por ele. Impossível de adivinhar (128 bits); vazio em pedidos antigos.
    codigo = models.CharField(max_length=32, unique=True, null=True, blank=True, editable=False)

    class Meta:
        db_table = "pedidos"
        ordering = ["-data"]

    def __str__(self):
        return f"Pedido {self.id} - {self.cliente}"

    @property
    def cliente(self):
        """Nome para mostrar: o usuário da conta ou, na compra sem conta, quem recebe."""
        if self.usuario_id:
            return self.usuario.get_username()
        return f"{self.entrega_nome or 'Cliente'} (visitante)"

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = secrets.token_urlsafe(16)
        super().save(*args, **kwargs)

    @classmethod
    def com_item(cls, produto, tamanho, quantidade=1, preco_unitario=None, **campos):
        """Pedido de uma peça só (painel, simulação, dados de exemplo e testes)."""
        pedido = cls.objects.create(**campos)
        pedido.itens.create(produto=produto, tamanho=tamanho, quantidade=quantidade, preco_unitario=preco_unitario)
        return pedido

    # As contas usam itens.all(): com prefetch_related("itens") não vão ao banco de novo
    @property
    def total(self):
        """Soma das peças, sem o frete."""
        return sum((i.total for i in self.itens.all()), Decimal(0))

    @property
    def quantidade(self):
        """Total de peças do pedido."""
        return sum(i.quantidade for i in self.itens.all())

    @property
    def total_com_frete(self):
        return self.total + self.frete

    @property
    def resumo(self):
        """"2× Camiseta Grid (M), 1× Boné Drop (U)" """
        return ", ".join(f"{i.quantidade}× {i.produto.nome} ({i.tamanho})" for i in self.itens.all())


class ItemPedido(models.Model):
    """Uma peça do pedido: produto, tamanho, quantidade e o preço pago."""
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="itens")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT)
    tamanho = models.CharField(max_length=2, choices=TAMANHOS)
    quantidade = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    # preço do produto no momento da compra: se o preço do produto mudar depois,
    # o total dos pedidos antigos continua o mesmo
    # blank=True: no admin pode ficar vazio e o save() copia o preço atual do produto
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2, blank=True,
                                         validators=[MinValueValidator(0)])

    class Meta:
        db_table = "itens_pedido"
        ordering = ["id"]
        verbose_name = "item do pedido"
        verbose_name_plural = "itens do pedido"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantidade__gte=1), name="item_quantidade_minima_1"),
            models.CheckConstraint(condition=models.Q(preco_unitario__gte=0), name="item_preco_unitario_nao_negativo"),
        ]

    def __str__(self):
        return f"{self.quantidade}× {self.produto} ({self.tamanho})"

    def save(self, *args, **kwargs):
        # Sem preço informado (ex.: item criado pelo /admin/), grava o preço do produto agora
        if self.preco_unitario is None and self.produto_id:
            self.preco_unitario = self.produto.preco
        super().save(*args, **kwargs)

    @property
    def total(self):
        return (self.preco_unitario or Decimal(0)) * self.quantidade
