from django import forms

from core.forms import CrispyFormMixin

from .models import Category, Kind, MonthClosing, Movement, Transfer, TreasurySettings


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

    def clean(self):
        cleaned = super().clean()
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
