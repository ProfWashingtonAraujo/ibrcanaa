from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .audit import ACTION_CHOICES


class Account(models.TextChoices):
    CASH = 'cash', 'Caixa'
    BANK = 'bank', 'Banco'


class Method(models.TextChoices):
    CASH = 'cash', 'Dinheiro'
    PIX = 'pix', 'Pix'
    OTHER = 'other', 'Outra'


class Kind(models.TextChoices):
    INCOME = 'income', 'Entrada'
    EXPENSE = 'expense', 'Saída'


class Status(models.TextChoices):
    PENDING = 'pending', 'A confirmar'
    CONFIRMED = 'confirmed', 'Confirmado'
    REJECTED = 'rejected', 'Recusado'


class Source(models.TextChoices):
    TREASURY = 'treasury', 'Tesouraria'
    PORTAL = 'portal', 'Portal'


def _money(label, **kwargs):
    return models.DecimalField(label, max_digits=12, decimal_places=2, **kwargs)


class TreasurySettings(models.Model):
    """Configuração única (pk=1): data de início e saldos de abertura."""

    start_date = models.DateField('início da tesouraria')
    opening_cash = _money('saldo inicial do caixa', default=Decimal('0.00'))
    opening_bank = _money('saldo inicial do banco', default=Decimal('0.00'))

    class Meta:
        verbose_name = 'configuração da tesouraria'
        verbose_name_plural = 'configuração da tesouraria'

    @classmethod
    def get(cls):
        return cls.objects.filter(pk=1).first()

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class Category(models.Model):
    name = models.CharField('nome', max_length=80)
    kind = models.CharField('tipo', max_length=10, choices=Kind.choices)
    is_special = models.BooleanField('oferta especial', default=False)
    is_tithe = models.BooleanField('conta para a relação de dizimistas', default=False)
    active = models.BooleanField('ativa', default=True)

    class Meta:
        verbose_name = 'categoria'
        verbose_name_plural = 'categorias'
        ordering = ['kind', 'name']
        constraints = [models.UniqueConstraint(fields=['name', 'kind'], name='tesouraria_category_unique_name_kind')]

    def __str__(self):
        return self.name

    def in_use(self):
        """Tasks 8 e 9 estendem para contas a pagar e recorrentes."""
        return self.movement_set.exists()


class MovementQuerySet(models.QuerySet):
    def live(self):
        return self.filter(deleted_at__isnull=True)

    def confirmed(self):
        return self.filter(status=Status.CONFIRMED)


class Movement(models.Model):
    date = models.DateField('data')
    kind = models.CharField('tipo', max_length=10, choices=Kind.choices)
    amount = _money('valor')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name='categoria')
    description = models.CharField('descrição', max_length=180)
    account = models.CharField('conta', max_length=10, choices=Account.choices, null=True, blank=True)
    method = models.CharField('forma', max_length=10, choices=Method.choices, default=Method.CASH)
    status = models.CharField('situação', max_length=10, choices=Status.choices, default=Status.CONFIRMED)
    source = models.CharField('origem', max_length=10, choices=Source.choices, default=Source.TREASURY)
    member = models.ForeignKey('core.Member', on_delete=models.SET_NULL, null=True, blank=True,
                               verbose_name='membro')
    destination = models.CharField('destino', max_length=120, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+', verbose_name='criado por')
    rejection_reason = models.TextField('motivo da recusa', blank=True)
    deleted_at = models.DateTimeField('excluído em', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = MovementQuerySet.as_manager()

    class Meta:
        verbose_name = 'movimento'
        verbose_name_plural = 'movimentos'
        ordering = ['-date', '-id']

    def __str__(self):
        return f'{self.get_kind_display()} {self.amount} em {self.date}'


class Transfer(models.Model):
    date = models.DateField('data')
    from_account = models.CharField('conta de origem', max_length=10, choices=Account.choices)
    to_account = models.CharField('conta de destino', max_length=10, choices=Account.choices)
    amount = _money('valor')
    note = models.CharField('observação', max_length=180, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+', verbose_name='criado por')
    deleted_at = models.DateTimeField('excluída em', null=True, blank=True)

    class Meta:
        verbose_name = 'transferência'
        verbose_name_plural = 'transferências'
        ordering = ['-date', '-id']

    def clean(self):
        if self.from_account == self.to_account:
            raise ValidationError('A conta de origem deve ser diferente da conta de destino.')
        if self.amount is None or self.amount <= 0:
            raise ValidationError('O valor deve ser maior que zero.')


class MonthClosing(models.Model):
    month = models.DateField('mês', unique=True)
    counted_cash = _money('caixa contado', null=True, blank=True)
    counted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+', verbose_name='contado por')
    counted_at = models.DateTimeField('contado em', null=True, blank=True)
    closed_at = models.DateTimeField('fechado em', null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='+', verbose_name='fechado por')
    opening_cash = _money('caixa na abertura', null=True, blank=True)
    opening_bank = _money('banco na abertura', null=True, blank=True)
    closing_cash = _money('caixa no fechamento', null=True, blank=True)
    closing_bank = _money('banco no fechamento', null=True, blank=True)
    notes = models.TextField('observações', blank=True)

    class Meta:
        verbose_name = 'fechamento do mês'
        verbose_name_plural = 'fechamentos do mês'
        ordering = ['-month']

    @property
    def is_closed(self):
        return self.closed_at is not None


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='+', verbose_name='usuário')
    at = models.DateTimeField('quando', auto_now_add=True)
    action = models.CharField('ação', max_length=20, choices=ACTION_CHOICES)
    model = models.CharField('modelo', max_length=60)
    object_id = models.CharField('objeto', max_length=40)
    summary = models.TextField('resumo')
    before = models.JSONField('antes', null=True, blank=True)
    after = models.JSONField('depois', null=True, blank=True)

    class Meta:
        verbose_name = 'registro de auditoria'
        verbose_name_plural = 'registros de auditoria'
        ordering = ['-at', '-id']
