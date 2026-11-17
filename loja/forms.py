from django import forms
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm, UserCreationForm
from django.contrib.auth.models import User

# Política de e-mail (vale para o cadastro da loja e para o /admin/):
#  - único sem diferenciar maiúsculas/minúsculas, entre contas com e-mail preenchido;
#  - e-mail vazio continua permitido (contas antigas/demonstrativas, createsuperuser sem e-mail);
#  - novos valores são gravados com strip() + minúsculas (contas existentes não são alteradas).
# A garantia final é o índice único auth_user_email_ci_uniq (migration 0005_email_unico):
# a validação abaixo só dá uma mensagem amigável antes de chegar no banco.
EMAIL_REPETIDO = "Já existe uma conta com este e-mail."


def normalizar_email(email):
    return (email or "").strip().lower()


def email_em_uso(email, exceto_pk=None):
    if not email:
        return False
    qs = User.objects.filter(email__iexact=email)
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
