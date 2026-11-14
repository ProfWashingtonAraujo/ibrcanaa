from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
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
        return self.movement_set.exists() or self.payable_set.exists() or self.recurringbill_set.exists()


class MovementQuerySet(models.QuerySet):
    def live(self):
        return self.filter(deleted_at__isnull=True)

    def confirmed(self):
        """Só filtra a situação: NÃO exclui movimentos excluídos (`deleted_at`).

        Código de saldo/resumo deve usar `counted()`.
        """
        return self.filter(status=Status.CONFIRMED)

    def counted(self):
        """Movimentos que entram em saldos: vivos e confirmados."""
        return self.live().confirmed()


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
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(status='confirmed') | models.Q(account__isnull=False),
                name='tesouraria_movement_confirmed_has_account'),
        ]

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


class RecurringBill(models.Model):
    """Modelo de conta que se repete todo mês (aluguel, luz) ou em parcelas (`installments`)."""

    description = models.CharField('descrição', max_length=180)
    payee = models.CharField('favorecido', max_length=120, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name='categoria')
    amount = _money('valor estimado')
    due_day = models.PositiveSmallIntegerField('dia do vencimento')
    start_date = models.DateField('primeiro mês')
    installments = models.PositiveSmallIntegerField('número de parcelas', null=True, blank=True)
    active = models.BooleanField('ativa', default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+', verbose_name='criada por')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'conta recorrente'
        verbose_name_plural = 'contas recorrentes'
        ordering = ['-active', 'description', 'id']
        constraints = [
            models.CheckConstraint(condition=models.Q(due_day__gte=1, due_day__lte=31),
                                   name='tesouraria_recurring_due_day_1_31'),
        ]

    def __str__(self):
        return self.description


class Payable(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', 'Em aberto'
        PAID = 'paid', 'Paga'
        CANCELED = 'canceled', 'Cancelada'

    description = models.CharField('descrição', max_length=180)
    payee = models.CharField('favorecido', max_length=120, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name='categoria')
    amount = _money('valor previsto')
    due_date = models.DateField('vencimento')
    status = models.CharField('situação', max_length=10, choices=Status.choices, default=Status.OPEN)
    movement = models.OneToOneField(Movement, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='payable', verbose_name='saída gerada')
    paid_amount = _money('valor pago', null=True, blank=True)
    paid_date = models.DateField('data do pagamento', null=True, blank=True)
    recurring = models.ForeignKey(RecurringBill, on_delete=models.SET_NULL, null=True, blank=True,
                                  verbose_name='recorrência')
    period = models.DateField('mês de referência', null=True, blank=True)
    installment_number = models.PositiveSmallIntegerField('parcela', null=True, blank=True)
    installments_total = models.PositiveSmallIntegerField('total de parcelas', null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+', verbose_name='criada por')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'conta a pagar'
        verbose_name_plural = 'contas a pagar'
        ordering = ['due_date', 'id']
        constraints = [
            models.UniqueConstraint(fields=['recurring', 'period'], condition=models.Q(recurring__isnull=False),
                                    name='tesouraria_payable_unique_recurring_period'),
        ]

    def __str__(self):
        return f'{self.description} ({self.due_date})'


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


class CommitteeOpinion(models.Model):
    """Parecer de um membro da Comissão de Contas sobre um mês fechado (um por mês e autor)."""

    TEXT_MAX = 2000

    class Result(models.TextChoices):
        APPROVED = 'approved', 'Aprovado'
        RESERVATIONS = 'reservations', 'Aprovado com ressalvas'

    month = models.DateField('mês')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+',
                               verbose_name='autor')
    result = models.CharField('parecer', max_length=20, choices=Result.choices)
    text = models.TextField('observações', blank=True, max_length=TEXT_MAX,
                            validators=[MaxLengthValidator(TEXT_MAX)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'parecer da Comissão de Contas'
        verbose_name_plural = 'pareceres da Comissão de Contas'
        ordering = ['month', 'created_at', 'id']
        constraints = [models.UniqueConstraint(fields=['month', 'author'], name='tesouraria_opinion_unique_month_author')]

    def __str__(self):
        return f'Parecer de {self.month:%m/%Y}: {self.get_result_display()}'
