from decimal import Decimal

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, Field, Layout
from dal import autocomplete
from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import AccessProfile, BibleNote, ContactLead, Event, Member, Ministry, Transaction


class CrispyFormMixin:
    full_width_fields = set()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.layout = Layout(
            Div(
                *(
                    Field(name, wrapper_class='full' if name in self.full_width_fields else '')
                    for name in self.fields
                ),
                css_class='form-grid',
            )
        )


class ContactLeadForm(CrispyFormMixin, forms.ModelForm):
    full_width_fields = {'message'}

    class Meta:
        model = ContactLead
        fields = ['name', 'email', 'whatsapp', 'interest', 'message']
        widgets = {'message': forms.Textarea(attrs={'rows': 4})}


class MemberForm(CrispyFormMixin, forms.ModelForm):
    username = forms.CharField(label='Usuário de acesso', max_length=150)
    photo = forms.ImageField(
        label='Foto do membro',
        required=False,
        help_text='JPG, PNG ou WebP. Recomendado: imagem quadrada de até 5 MB.',
        widget=forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
    )
    password1 = forms.CharField(
        label='Senha',
        required=False,
        widget=forms.PasswordInput,
        help_text='Na edição, deixe em branco para manter a senha atual.',
    )
    password2 = forms.CharField(
        label='Confirmar senha',
        required=False,
        widget=forms.PasswordInput,
    )
    full_width_fields = {'photo', 'username'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ministry'].label = 'Ministério'
        if self.instance.pk and self.instance.user_id:
            self.fields['username'].initial = self.instance.user.username
            profile, _ = AccessProfile.objects.get_or_create(user=self.instance.user)
            self.fields['photo'].initial = profile.photo
        if not self.instance.pk or not self.instance.user_id:
            self.fields['password1'].required = True
            self.fields['password2'].required = True

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo and photo.size > 5 * 1024 * 1024:
            raise ValidationError('A foto deve ter no máximo 5 MB.')
        return photo

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        users = User.objects.filter(username__iexact=username)
        if self.instance.user_id:
            users = users.exclude(pk=self.instance.user_id)
        if users.exists():
            raise ValidationError('Este usuário já está em uso.')
        return username

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 or password2:
            if password1 != password2:
                self.add_error('password2', 'As senhas não coincidem.')
            elif password1:
                candidate = self.instance.user if self.instance.user_id else User(
                    username=cleaned_data.get('username', ''),
                    email=cleaned_data.get('email', ''),
                )
                try:
                    password_validation.validate_password(password1, candidate)
                except ValidationError as error:
                    self.add_error('password1', error)
        return cleaned_data

    def save(self, commit=True):
        member = super().save(commit=False)
        user = member.user if member.user_id else User()
        names = member.name.split(maxsplit=1)
        user.username = self.cleaned_data['username']
        user.email = member.email
        user.first_name = names[0]
        user.last_name = names[1] if len(names) > 1 else ''
        user.is_active = True
        if self.cleaned_data.get('password1'):
            user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            profile, _ = AccessProfile.objects.update_or_create(user=user, defaults={'role': AccessProfile.Role.MEMBER})
            if self.cleaned_data.get('photo'):
                profile.photo = self.cleaned_data['photo']
                profile.save(update_fields=['photo'])
            member.user = user
            member.save()
            self.save_m2m()
        return member

    class Meta:
        model = Member
        fields = ['name', 'email', 'phone', 'ministry', 'status', 'frequency', 'baptized']


class EventForm(CrispyFormMixin, forms.ModelForm):
    full_width_fields = {'description'}

    class Meta:
        model = Event
        fields = ['title', 'starts_at', 'kind', 'location', 'expected_attendance', 'description']
        widgets = {
            'starts_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class MinistryForm(CrispyFormMixin, forms.ModelForm):
    members = forms.ModelMultipleChoiceField(
        label='Membros participantes',
        queryset=Member.objects.none(),
        required=False,
        help_text='Informação interna. Estes nomes não serão exibidos publicamente.',
        widget=forms.SelectMultiple(attrs={'size': 10}),
    )
    full_width_fields = {'description', 'members'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['members'].queryset = Member.objects.select_related('ministry').order_by('name')
        if self.instance.pk:
            self.fields['members'].initial = self.instance.members.all()

    def save(self, commit=True):
        ministry = super().save(commit=commit)
        if commit:
            selected_members = self.cleaned_data['members']
            ministry.members.exclude(pk__in=selected_members).update(ministry=None)
            selected_members.update(ministry=ministry)
        return ministry

    class Meta:
        model = Ministry
        fields = ['name', 'leader_name', 'description', 'status', 'members']
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Apresente o propósito e as atividades do ministério.',
            }),
        }


class TransactionForm(CrispyFormMixin, forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['date', 'description', 'category', 'kind', 'amount', 'member']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}


class MemberContributionForm(forms.Form):
    category = forms.ChoiceField(
        label='Tipo de contribuição',
        choices=(('Dízimos', 'Dízimo'), ('Ofertas', 'Oferta')),
        widget=forms.RadioSelect,
    )
    amount = forms.DecimalField(
        label='Valor',
        min_value=Decimal('1.00'),
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'min': '1', 'step': '0.01', 'placeholder': '0,00'}),
    )
    note = forms.CharField(
        label='Observação',
        required=False,
        max_length=120,
        widget=forms.TextInput(attrs={'placeholder': 'Opcional'}),
    )


class BibleNoteForm(forms.ModelForm):
    class Meta:
        model = BibleNote
        fields = ['content']
        widgets = {'content': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Escreva o que Deus falou ao seu coração...'})}


class UserAccountForm(CrispyFormMixin, forms.ModelForm):
    role = forms.ChoiceField(label='Classificação', choices=AccessProfile.Role.choices)
    member = forms.ModelChoiceField(
        label='Perfil de membro vinculado',
        queryset=Member.objects.none(),
        required=False,
        help_text='Opcional para contas administrativas; recomendado para membro, visitante ou criança.',
        widget=autocomplete.ModelSelect2(
            url='member_autocomplete',
            attrs={'data-placeholder': 'Digite o nome ou e-mail do membro', 'data-minimum-input-length': 1},
        ),
    )
    photo = forms.ImageField(
        label='Foto do usuário',
        required=False,
        help_text='JPG, PNG ou WebP. Recomendado: imagem quadrada de até 5 MB.',
        widget=forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
    )
    password1 = forms.CharField(
        label='Senha', required=False, widget=forms.PasswordInput,
        help_text='Na edição, deixe em branco para manter a senha atual.',
    )
    password2 = forms.CharField(label='Confirmar senha', required=False, widget=forms.PasswordInput)
    full_width_fields = {'username', 'email', 'member', 'photo'}

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['email'].required = True
        available_members = Member.objects.filter(user__isnull=True)
        if self.instance.pk:
            available_members = Member.objects.filter(Q(user__isnull=True) | Q(user=self.instance))
            profile, _ = AccessProfile.objects.get_or_create(
                user=self.instance,
                defaults={'role': AccessProfile.Role.BOARD if self.instance.is_staff else AccessProfile.Role.MEMBER},
            )
            self.fields['role'].initial = profile.role
            self.fields['member'].initial = getattr(self.instance, 'member_profile', None)
            self.fields['photo'].initial = profile.photo
        else:
            self.fields['password1'].required = True
            self.fields['password2'].required = True
        self.fields['member'].queryset = available_members.select_related('ministry')

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo and photo.size > 5 * 1024 * 1024:
            raise ValidationError('A foto deve ter no máximo 5 MB.')
        return photo

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        users = User.objects.filter(username__iexact=username)
        if self.instance.pk:
            users = users.exclude(pk=self.instance.pk)
        if users.exists():
            raise ValidationError('Este usuário já está em uso.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        users = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            users = users.exclude(pk=self.instance.pk)
        if users.exists():
            raise ValidationError('Este e-mail já está vinculado a outro usuário.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 or password2:
            if password1 != password2:
                self.add_error('password2', 'As senhas não coincidem.')
            elif password1:
                try:
                    password_validation.validate_password(password1, self.instance)
                except ValidationError as error:
                    self.add_error('password1', error)
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        role = self.cleaned_data['role']
        user.is_staff = role in AccessProfile.ADMIN_ROLES
        if self.cleaned_data.get('password1'):
            user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            profile, _ = AccessProfile.objects.update_or_create(user=user, defaults={'role': role})
            if self.cleaned_data.get('photo'):
                profile.photo = self.cleaned_data['photo']
                profile.save(update_fields=['photo'])
            selected_member = self.cleaned_data.get('member')
            Member.objects.filter(user=user).exclude(pk=getattr(selected_member, 'pk', None)).update(user=None)
            if selected_member:
                selected_member.user = user
                selected_member.save(update_fields=['user'])
        return user


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.layout = Layout(
            Div(
                Field('username', placeholder='Seu usuário'),
                Field('password', placeholder='Sua senha'),
                css_class='login-fields',
            )
        )
