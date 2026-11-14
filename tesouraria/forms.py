from decimal import Decimal

from django import forms
from django.db.models import Q

from core.forms import CrispyFormMixin

from core.models import Member

from .models import Account, Category, Kind, Method, MonthClosing, Movement, Payable, Transfer, TreasurySettings


def active_categories(kind):
    """Categorias que podem ser escolhidas em novos lançamentos (as arquivadas ficam de fora)."""
    return Category.objects.filter(active=True, kind=kind)


class SettingsForm(CrispyFormMixin, forms.ModelForm):
    class Meta:
        model = TreasurySettings
        fields = ['start_date', 'opening_cash', 'opening_bank']
        widgets = {'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}
        labels = {'start_date': 'Data de início da tesouraria',
                  'opening_cash': 'Saldo inicial do caixa (R$)',
                  'opening_bank': 'Saldo inicial do banco (R$)'}

    @staticmethod
    def is_locked():
        return MonthClosing.objects.filter(closed_at__isnull=False).exists()

    def clean(self):
        cleaned = super().clean()
        if self.is_locked():
            raise forms.ValidationError(
                'A abertura não pode ser alterada porque já existe mês fechado. Reabra os meses fechados antes.')
        return cleaned

    def clean_start_date(self):
        start = self.cleaned_data['start_date']
        dates = [Movement.objects.live().order_by('date').values_list('date', flat=True).first(),
                 Transfer.objects.filter(deleted_at__isnull=True).order_by('date')
                 .values_list('date', flat=True).first()]
        oldest = min((d for d in dates if d), default=None)
        if oldest and start > oldest:
            raise forms.ValidationError(
                f'Já existe lançamento em {oldest:%d/%m/%Y}, anterior à nova data. '
                'Use uma data de início igual ou anterior a ele.')
        return start


class CategoryForm(CrispyFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'kind', 'is_special', 'is_tithe']

    LOCKED_FIELDS = ('kind', 'is_special', 'is_tithe')
    LOCKED_HELP = 'Esta categoria já tem lançamentos; para mudar o significado, crie outra categoria.'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.locked = bool(self.instance.pk and self.instance.in_use())
        self.attempted_change = False
        if not self.locked:
            return
        for name in self.LOCKED_FIELDS:
            field = self.fields[name]
            if self.is_bound:
                posted = field.widget.value_from_datadict(self.data, self.files, self.add_prefix(name))
                # Campos desabilitados não são enviados pelo navegador; só conta o que veio diferente.
                if posted not in (None, '', False) and posted != getattr(self.instance, name):
                    self.attempted_change = True
            field.disabled = True
            field.help_text = self.LOCKED_HELP

    def clean(self):
        cleaned = super().clean()
        if self.attempted_change:
            raise forms.ValidationError(
                'Esta categoria já tem lançamentos: tipo e marcações não podem ser alterados. '
                'Para mudar o significado, crie outra categoria.')
        name, kind = cleaned.get('name'), cleaned.get('kind')
        if name and kind:
            clash = Category.objects.filter(name__iexact=name.strip(), kind=kind).exclude(pk=self.instance.pk)
            if clash.exists():
                self.add_error('name', 'Já existe uma categoria com este nome neste tipo.')
        if kind != Kind.INCOME and (cleaned.get('is_special') or cleaned.get('is_tithe')):
            raise forms.ValidationError('Oferta especial e relação de dizimistas valem só para entradas.')
        if cleaned.get('is_special') and cleaned.get('is_tithe'):
            raise forms.ValidationError('Uma categoria não pode ser oferta especial e de dizimistas ao mesmo tempo.')
        return cleaned

    def clean_name(self):
        return self.cleaned_data['name'].strip()


TITHE_HINT = 'Informe o membro para ele constar na relação de dizimistas'
DATE_WIDGET = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')


def _positive_amount(value):
    if value <= 0:
        raise forms.ValidationError('O valor deve ser maior que zero.')
    return value


class MovementForm(CrispyFormMixin, forms.Form):
    full_width_fields = {'description'}

    date = forms.DateField(label='Data', widget=DATE_WIDGET)
    category = forms.ModelChoiceField(label='Categoria', queryset=Category.objects.none())
    description = forms.CharField(label='Descrição', max_length=180)
    amount = forms.DecimalField(label='Valor (R$)', max_digits=12, decimal_places=2, validators=[_positive_amount],
                                widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}))
    method = forms.ChoiceField(label='Forma', choices=Method.choices, initial=Method.CASH)
    account = forms.ChoiceField(label='Conta', choices=Account.choices, initial=Account.CASH,
                                help_text='Sugerida pela forma: dinheiro no Caixa, Pix e outras no Banco. '
                                          'Você pode trocar.')
    member = forms.ModelChoiceField(label='Membro', queryset=Member.objects.none(), required=False,
                                    help_text='Opcional. Para dízimos, informe o membro para ele constar na '
                                              'relação de dizimistas.')
    destination = forms.CharField(label='Destino da oferta especial', max_length=120, required=False,
                                  help_text='Obrigatório quando a categoria é oferta especial.')

    def __init__(self, *args, kind=Kind.INCOME, current_category=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind
        allowed = active_categories(kind)
        if current_category is not None:  # categoria arquivada continua valendo para quem já a usa
            allowed = Category.objects.filter(Q(pk__in=allowed.values('pk')) | Q(pk=current_category.pk))
        self.fields['category'].queryset = allowed
        self.fields['member'].queryset = Member.objects.order_by('name')
        if kind != Kind.INCOME:
            del self.fields['member']
        self.tithe_without_member = False

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get('category')
        if category is not None:
            if category.is_special:
                if not (cleaned.get('destination') or '').strip():
                    self.add_error('destination', 'Informe o destino da oferta especial.')
            else:
                cleaned['destination'] = ''
            self.tithe_without_member = bool(category.is_tithe and not cleaned.get('member'))
        return cleaned

    def clean_description(self):
        return self.cleaned_data['description'].strip()

    def clean_amount(self):
        value = self.cleaned_data['amount']
        if value.quantize(Decimal('0.01')) != value:
            raise forms.ValidationError('Use no máximo duas casas decimais.')
        return value

    @classmethod
    def initial_from(cls, movement):
        return {name: getattr(movement, name) for name in
                ('date', 'category', 'description', 'amount', 'account', 'method', 'member', 'destination')}


class TransferForm(CrispyFormMixin, forms.Form):
    from_account = forms.ChoiceField(label='Sai da conta', choices=Account.choices, initial=Account.CASH)
    to_account = forms.ChoiceField(label='Entra na conta', choices=Account.choices, initial=Account.BANK)
    date = forms.DateField(label='Data', widget=DATE_WIDGET)
    amount = forms.DecimalField(label='Valor (R$)', max_digits=12, decimal_places=2, validators=[_positive_amount],
                                widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}))
    note = forms.CharField(label='Observação', max_length=180, required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('from_account') and cleaned.get('from_account') == cleaned.get('to_account'):
            raise forms.ValidationError('A conta de origem deve ser diferente da conta de destino.')
        return cleaned


class ConfirmPendingForm(forms.Form):
    account = forms.ChoiceField(label='Conta', choices=Account.choices, initial=Account.BANK)
    method = forms.ChoiceField(label='Forma', choices=Method.choices, initial=Method.PIX)
    date = forms.DateField(label='Data em que entrou', widget=DATE_WIDGET)


class RejectPendingForm(forms.Form):
    reason = forms.CharField(label='Motivo da recusa', max_length=500,
                             error_messages={'required': 'Informe o motivo da recusa.'},
                             widget=forms.TextInput(attrs={'placeholder': 'Motivo da recusa'}))


class PayableForm(CrispyFormMixin, forms.Form):
    full_width_fields = {'description'}

    description = forms.CharField(label='Descrição', max_length=180)
    payee = forms.CharField(label='Favorecido', max_length=120, required=False)
    category = forms.ModelChoiceField(label='Categoria', queryset=Category.objects.none())
    amount = forms.DecimalField(label='Valor previsto (R$)', max_digits=12, decimal_places=2,
                                validators=[_positive_amount],
                                widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}))
    due_date = forms.DateField(label='Vencimento', widget=DATE_WIDGET)

    def __init__(self, *args, current_category=None, **kwargs):
        super().__init__(*args, **kwargs)
        allowed = active_categories(Kind.EXPENSE)
        if current_category is not None:  # categoria arquivada continua valendo na conta que já a usa
            allowed = Category.objects.filter(Q(pk__in=allowed.values('pk')) | Q(pk=current_category.pk))
        self.fields['category'].queryset = allowed

    def clean_description(self):
        return self.cleaned_data['description'].strip()

    def clean_amount(self):
        value = self.cleaned_data['amount']
        if value.quantize(Decimal('0.01')) != value:
            raise forms.ValidationError('Use no máximo duas casas decimais.')
        return value

    @classmethod
    def initial_from(cls, payable):
        return {name: getattr(payable, name) for name in
                ('description', 'payee', 'category', 'amount', 'due_date')}


class PayForm(CrispyFormMixin, forms.Form):
    paid_amount = forms.DecimalField(label='Valor pago (R$)', max_digits=12, decimal_places=2,
                                     validators=[_positive_amount],
                                     widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}))
    paid_date = forms.DateField(label='Data do pagamento', widget=DATE_WIDGET)
    method = forms.ChoiceField(label='Forma', choices=Method.choices, initial=Method.PIX)
    account = forms.ChoiceField(label='Conta', choices=Account.choices, initial=Account.BANK,
                                help_text='Sugerida pela forma: dinheiro no Caixa, Pix e outras no Banco. '
                                          'Você pode trocar.')

    def clean_paid_amount(self):
        value = self.cleaned_data['paid_amount']
        if value.quantize(Decimal('0.01')) != value:
            raise forms.ValidationError('Use no máximo duas casas decimais.')
        return value


class RecurringForm(CrispyFormMixin, forms.Form):
    full_width_fields = {'description'}

    description = forms.CharField(label='Descrição', max_length=180)
    payee = forms.CharField(label='Favorecido', max_length=120, required=False)
    category = forms.ModelChoiceField(label='Categoria', queryset=Category.objects.none())
    amount = forms.DecimalField(label='Valor estimado (R$)', max_digits=12, decimal_places=2,
                                validators=[_positive_amount],
                                widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}))
    due_day = forms.IntegerField(label='Dia do vencimento', min_value=1, max_value=31,
                                 help_text='Em meses mais curtos, vale o último dia do mês.')
    start_date = forms.DateField(label='Primeiro mês', widget=DATE_WIDGET,
                                 help_text='A primeira conta é a do mês desta data (parcela 1).')
    installments = forms.IntegerField(label='Número de parcelas', required=False, min_value=1, max_value=600,
                                      help_text='Deixe em branco para uma conta fixa, sem fim.')

    def __init__(self, *args, current_category=None, **kwargs):
        super().__init__(*args, **kwargs)
        allowed = active_categories(Kind.EXPENSE)
        if current_category is not None:  # categoria arquivada continua valendo na recorrência que já a usa
            allowed = Category.objects.filter(Q(pk__in=allowed.values('pk')) | Q(pk=current_category.pk))
        self.fields['category'].queryset = allowed

    def clean_description(self):
        return self.cleaned_data['description'].strip()

    def clean_amount(self):
        value = self.cleaned_data['amount']
        if value.quantize(Decimal('0.01')) != value:
            raise forms.ValidationError('Use no máximo duas casas decimais.')
        return value

    @classmethod
    def initial_from(cls, bill):
        return {name: getattr(bill, name) for name in
                ('description', 'payee', 'category', 'amount', 'due_day', 'start_date', 'installments')}
