from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class CadastroForm(UserCreationForm):
    """Cadastro de cliente: username + e-mail + senha (2x).

    Só esses campos existem no form, então is_staff/is_superuser enviados
    no POST são ignorados: quem se cadastra pela loja é sempre cliente comum.
    """

    email = forms.EmailField(label="E-mail", max_length=254)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
        return user
