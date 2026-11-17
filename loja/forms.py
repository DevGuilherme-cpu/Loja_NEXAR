from django import forms
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.files.uploadedfile import UploadedFile
from django.db.models.functions import Lower, Trim

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


def enviado_agora(arquivo):
    """True só para arquivo novo do POST (não para o valor que já estava gravado no produto)."""
    return isinstance(arquivo, UploadedFile)


class ProdutoForm(forms.ModelForm):
    cor = forms.RegexField(
        label="Cor da peça", regex=COR_REGEX, required=False, max_length=7,
        error_messages={"invalid": "Cor inválida: use o formato #RRGGBB (ex.: #1F2F6B)."},
    )

    class Meta:
        model = Produto
        fields = ["nome", "descricao", "preco", "estoque", "categoria", "cor", "imagem", "imagem_2", "modelo_3d"]
        labels = {
            "nome": "Nome", "descricao": "Descrição", "preco": "Preço (R$)", "estoque": "Estoque",
            "categoria": "Categoria", "imagem": "Foto", "imagem_2": "Foto vestindo", "modelo_3d": "Modelo 3D (.glb)",
        }
        error_messages = {
            "imagem": {"invalid_image": "Envie uma imagem válida (JPG, PNG, WebP...). O arquivo enviado não é uma imagem."},
            "imagem_2": {"invalid_image": "Envie uma imagem válida (JPG, PNG, WebP...). O arquivo enviado não é uma imagem."},
            "categoria": {"invalid_choice": "Categoria inexistente. Escolha uma categoria da lista."},
        }

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
        arquivo.seek(0)
        cabecalho = arquivo.read(4)
        arquivo.seek(0)
        if cabecalho != b"glTF":
            raise forms.ValidationError("Arquivo .glb inválido: não é um glTF binário (glTF 2.0).", code="cabecalho")
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
