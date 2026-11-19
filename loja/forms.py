from decimal import Decimal

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.files.uploadedfile import UploadedFile
from django.db.models.functions import Lower, Trim

from .glb import validar_glb
from .models import Categoria, Produto

# Política de e-mail (vale para o cadastro da loja e para o /admin/):
#  - único sem diferenciar maiúsculas/minúsculas nem espaços nas pontas, entre contas com e-mail preenchido;
#  - e-mail vazio continua permitido (contas antigas/demonstrativas, createsuperuser sem e-mail);
#  - novos valores são gravados com strip() + minúsculas (contas existentes não são alteradas).
# A garantia final é o índice único auth_user_email_ci_uniq (migration 0005_email_unico):
# a validação abaixo só dá uma mensagem amigável antes de chegar no banco.
# Limites conhecidos: createsuperuser/shell não normalizam (o índice ainda barra duplicata, com
# IntegrityError); no /admin/, dois cadastros simultâneos do mesmo e-mail viram erro 500 no segundo
# (só a equipe usa o admin; o cadastro da loja trata a corrida e mostra erro no formulário).
EMAIL_REPETIDO = "Já existe uma conta com este e-mail."


def normalizar_email(email):
    return (email or "").strip().lower()


def email_em_uso(email, exceto_pk=None):
    if not email:
        return False
    # mesma regra do índice da 0005: LOWER(TRIM(email)) (pega também contas antigas com espaços)
    qs = User.objects.annotate(email_norm=Lower(Trim("email"))).filter(email_norm=email.strip().lower())
    if exceto_pk is not None:
        qs = qs.exclude(pk=exceto_pk)
    return qs.exists()


class EmailUnicoMixin:
    """clean_email comum: normaliza e recusa e-mail já usado por OUTRA conta."""

    def clean_email(self):
        email = normalizar_email(self.cleaned_data.get("email"))
        if email_em_uso(email, exceto_pk=self.instance.pk):
            raise forms.ValidationError(EMAIL_REPETIDO, code="email_repetido")
        return email


class CadastroForm(EmailUnicoMixin, UserCreationForm):
    """Cadastro de cliente: username + e-mail + senha (2x).

    Só esses campos existem no form, então is_staff/is_superuser enviados
    no POST são ignorados: quem se cadastra pela loja é sempre cliente comum.
    """

    email = forms.EmailField(label="E-mail", max_length=254)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
        return user


class AdminCriarUsuarioForm(EmailUnicoMixin, AdminUserCreationForm):
    """/admin/auth/user/add/: e-mail opcional, mas se preenchido segue a política."""

    email = forms.EmailField(label="E-mail", max_length=254, required=False)

    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class AdminEditarUsuarioForm(EmailUnicoMixin, UserChangeForm):
    """Edição no admin: valida o e-mail ignorando o próprio usuário."""

    class Meta(UserChangeForm.Meta):
        model = User


# ---------- painel: produtos e categorias ----------
# Uploads vão para MEDIA_ROOT (media/produtos/ e media/modelos/). Arquivos antigos não são
# apagados do disco ao substituir/excluir (pode haver outro produto usando o mesmo caminho).
IMAGEM_MAX_MB = 5
MODELO_MAX_MB = 15
CATEGORIA_REPETIDA = "Já existe uma categoria com este nome."
COR_REGEX = r"^#[0-9A-Fa-f]{6}$"
CAMPOS_ARQUIVO = ("imagem", "imagem_2", "modelo_3d")
UPLOADS_DESATIVADOS = ("Envio de arquivos está desativado neste ambiente (a hospedagem não guarda arquivos). "
                       "Os demais campos podem ser salvos sem anexos.")


def uploads_habilitados():
    """settings.UPLOADS_HABILITADOS (False na Vercel: disco efêmero e corpo da requisição ~4,5 MB)."""
    return getattr(settings, "UPLOADS_HABILITADOS", True)


def enviado_agora(arquivo):
    """True só para arquivo novo do POST (não para o valor que já estava gravado no produto)."""
    return isinstance(arquivo, UploadedFile)


class ProdutoForm(forms.ModelForm):
    cor = forms.RegexField(
        label="Cor da peça", regex=COR_REGEX, required=False, max_length=7,
        error_messages={"invalid": "Cor inválida: use o formato #RRGGBB (ex.: #1F2F6B)."},
    )
    # <input type=color> sempre envia uma cor; esta opção grava cor vazia (o 3D escolhe a cor sozinho)
    cor_automatica = forms.BooleanField(label="Cor automática", required=False)

    class Meta:
        model = Produto
        fields = ["nome", "descricao", "preco", "estoque", "categoria", "cor", "imagem", "imagem_2", "modelo_3d"]
        labels = {
            "nome": "Nome", "descricao": "Descrição", "preco": "Preço (R$)", "estoque": "Estoque",
            "categoria": "Categoria", "imagem": "Foto", "imagem_2": "Foto vestindo", "modelo_3d": "Modelo 3D (.glb)",
        }
        # FileInput simples: sem o "limpar" do ClearableFileInput (não há botão de remover na tela)
        widgets = {"imagem": forms.FileInput, "imagem_2": forms.FileInput, "modelo_3d": forms.FileInput}
        error_messages = {
            "imagem": {"invalid_image": "Envie uma imagem válida (JPG, PNG, WebP...). O arquivo enviado não é uma imagem."},
            "imagem_2": {"invalid_image": "Envie uma imagem válida (JPG, PNG, WebP...). O arquivo enviado não é uma imagem."},
            "categoria": {"invalid_choice": "Categoria inexistente. Escolha uma categoria da lista."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial["cor_automatica"] = not (self.instance and self.instance.cor)

    def clean(self):
        dados = super().clean()
        # nunca ignorar em silêncio um arquivo enviado quando o ambiente não guarda uploads
        if not uploads_habilitados() and any(self.files.get(c) for c in CAMPOS_ARQUIVO):
            self.add_error(None, forms.ValidationError(UPLOADS_DESATIVADOS, code="uploads_desativados"))
        if dados.get("cor_automatica"):
            dados["cor"] = ""
            self.errors.pop("cor", None)  # cor ignorada quando a automática está marcada
        return dados

    def clean_cor(self):
        return (self.cleaned_data.get("cor") or "").upper()

    def _imagem(self, campo):
        arquivo = self.cleaned_data.get(campo)
        if enviado_agora(arquivo) and arquivo.size > IMAGEM_MAX_MB * 1024 * 1024:
            raise forms.ValidationError(f"A imagem pode ter no máximo {IMAGEM_MAX_MB} MB.", code="grande")
        return arquivo

    def clean_imagem(self):
        return self._imagem("imagem")

    def clean_imagem_2(self):
        return self._imagem("imagem_2")

    def clean_modelo_3d(self):
        # sem arquivo novo, o FileField devolve o valor atual (ex.: /static/modelos/tenis.glb ou link): mantém
        arquivo = self.cleaned_data.get("modelo_3d")
        if not enviado_agora(arquivo):
            return arquivo
        if not arquivo.name.lower().endswith(".glb"):
            raise forms.ValidationError("O modelo 3D precisa ser um arquivo .glb.", code="extensao")
        if arquivo.size > MODELO_MAX_MB * 1024 * 1024:
            raise forms.ValidationError(f"O modelo 3D pode ter no máximo {MODELO_MAX_MB} MB.", code="grande")
        validar_glb(arquivo, MODELO_MAX_MB * 1024 * 1024)  # estrutura GLB 2.0 (ver loja/glb.py)
        return arquivo


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nome"]
        labels = {"nome": "Nome"}

    def clean_nome(self):
        nome = self.cleaned_data["nome"]  # CharField já faz strip() e exige valor
        # MySQL compara sem maiúsculas/minúsculas pelo collation; SQLite/PostgreSQL não: valida aqui
        if Categoria.objects.filter(nome__iexact=nome).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(CATEGORIA_REPETIDA, code="repetida")
        return nome


# ---------- checkout (entrega e pagamento simulado) ----------

FRETE_GRATIS_ACIMA = Decimal("300")
FRETES = {"padrao": Decimal("19.90"), "expresso": Decimal("34.90")}
UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI",
       "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]


def calcular_frete(subtotal, envio):
    """Padrão grátis acima de R$ 300; expresso sempre cobra (é o que paga a pressa)."""
    if envio == "padrao" and subtotal >= FRETE_GRATIS_ACIMA:
        return Decimal("0")
    return FRETES[envio]


def so_digitos(texto):
    return "".join(c for c in texto if c.isascii() and c.isdigit())


def cpf_valido(cpf):
    """Confere os dois dígitos verificadores (o mesmo cálculo da Receita)."""
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        if (soma * 10 % 11) % 10 != int(cpf[tamanho]):
            return False
    return True


class EntregaForm(forms.Form):
    nome = forms.CharField(label="Nome completo", max_length=100)
    cpf = forms.CharField(label="CPF", max_length=14)
    telefone = forms.CharField(label="Celular", max_length=16)
    cep = forms.CharField(label="CEP", max_length=9)
    endereco = forms.CharField(label="Rua ou avenida", max_length=120)
    numero = forms.CharField(label="Número", max_length=10)
    complemento = forms.CharField(label="Complemento", max_length=60, required=False)
    bairro = forms.CharField(label="Bairro", max_length=60)
    cidade = forms.CharField(label="Cidade", max_length=60)
    uf = forms.ChoiceField(label="Estado", choices=[(uf, uf) for uf in UFS])
    envio = forms.ChoiceField(label="Entrega", choices=[("padrao", "Padrão"), ("expresso", "Expresso")])
    pagamento = forms.ChoiceField(label="Pagamento", choices=[("pix", "Pix"), ("cartao", "Cartão"), ("boleto", "Boleto")])

    def clean_nome(self):
        nome = " ".join(self.cleaned_data["nome"].split())
        if len(nome.split()) < 2:
            raise forms.ValidationError("Digite nome e sobrenome.")
        return nome

    def clean_cpf(self):
        cpf = so_digitos(self.cleaned_data["cpf"])
        if not cpf_valido(cpf):
            raise forms.ValidationError("CPF inválido. Confira os números.")
        return cpf

    def clean_telefone(self):
        tel = so_digitos(self.cleaned_data["telefone"])
        if len(tel) not in (10, 11):
            raise forms.ValidationError("Digite o celular com DDD.")
        return tel

    def clean_cep(self):
        cep = so_digitos(self.cleaned_data["cep"])
        if len(cep) != 8:
            raise forms.ValidationError("O CEP tem 8 números.")
        return cep

    def dados_do_pedido(self, subtotal):
        """Campos do Pedido. O CPF completo não sai daqui: só os 2 últimos dígitos são gravados."""
        d = self.cleaned_data
        endereco = f"{d['endereco']}, {d['numero']}" + (f" ({d['complemento']})" if d["complemento"] else "")
        tel = d["telefone"]
        return {
            "entrega_nome": d["nome"],
            "entrega_cpf": f"***.***.***-{d['cpf'][-2:]}",
            "entrega_telefone": f"({tel[:2]}) {tel[2:-4]}-{tel[-4:]}",
            "entrega_cep": f"{d['cep'][:5]}-{d['cep'][5:]}",
            "entrega_endereco": endereco,
            "entrega_bairro": d["bairro"],
            "entrega_cidade": d["cidade"],
            "entrega_uf": d["uf"],
            "envio": d["envio"],
            "pagamento": d["pagamento"],
            "frete": calcular_frete(subtotal, d["envio"]),
        }
