from django.db import models
from django.contrib.auth.models import User


class AccessProfile(models.Model):
    class Role(models.TextChoices):
        PASTOR = 'pastor', 'Pastor'
        BOARD = 'board', 'Diretoria'
        DEACON = 'deacon', 'Diácono'
        SECRETARY = 'secretary', 'Secretário'
        TREASURER = 'treasurer', 'Tesoureiro'
        MEMBER = 'member', 'Membro'
        VISITOR = 'visitor', 'Visitante'
        CHILD = 'child', 'Criança'

    ADMIN_ROLES = {Role.PASTOR, Role.BOARD, Role.DEACON, Role.SECRETARY, Role.TREASURER}
    USER_MANAGER_ROLES = {Role.PASTOR, Role.BOARD}

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='access_profile')
    role = models.CharField('classificação', max_length=20, choices=Role, default=Role.MEMBER)
    photo = models.ImageField('foto', upload_to='usuarios/%Y/%m/', blank=True)

    class Meta:
        ordering = ['user__first_name', 'user__username']
        verbose_name = 'perfil de acesso'
        verbose_name_plural = 'perfis de acesso'

    def __str__(self):
        return f'{self.user} - {self.get_role_display()}'

    @property
    def can_manage_users(self):
        return self.role in self.USER_MANAGER_ROLES


class Ministry(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Ativo'
        RECRUITING = 'recruiting', 'Precisa de voluntários'

    name = models.CharField('nome', max_length=120, unique=True)
    leader_name = models.CharField('líder', max_length=120)
    description = models.TextField('descrição pública', blank=True, max_length=500)
    status = models.CharField('status', max_length=20, choices=Status, default=Status.ACTIVE)

    class Meta:
        ordering = ['name']
        verbose_name = 'ministério'
        verbose_name_plural = 'ministérios'

    def __str__(self):
        return self.name


class Member(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Ativo'
        LEADERSHIP = 'leadership', 'Liderança'
        VISITOR = 'visitor', 'Visitante'
        NEW = 'new', 'Novo'
        AWAY = 'away', 'Afastado'

    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='member_profile')
    name = models.CharField('nome', max_length=120)
    email = models.EmailField('e-mail', unique=True)
    phone = models.CharField('telefone', max_length=30, blank=True)
    ministries = models.ManyToManyField(Ministry, blank=True, related_name='members', verbose_name='ministérios')
    status = models.CharField('status', max_length=20, choices=Status, default=Status.ACTIVE)
    frequency = models.PositiveSmallIntegerField('frequência', default=0)
    baptized = models.BooleanField('batizado', default=False)
    avatar_url = models.URLField('avatar', blank=True)
    created_at = models.DateTimeField('cadastrado em', auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'membro'
        verbose_name_plural = 'membros'

    def __str__(self):
        return self.name


class Event(models.Model):
    calendar_event = models.OneToOneField(
        'swingtime.Event',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='church_event',
        verbose_name='evento da agenda',
    )
    title = models.CharField('título', max_length=160)
    starts_at = models.DateTimeField('início')
    kind = models.CharField('tipo', max_length=60)
    location = models.CharField('local', max_length=160)
    expected_attendance = models.PositiveIntegerField('público esperado', default=0)
    description = models.TextField('descrição', blank=True)

    class Meta:
        ordering = ['starts_at']
        verbose_name = 'evento'
        verbose_name_plural = 'eventos'

    def __str__(self):
        return self.title


class Transaction(models.Model):
    class Kind(models.TextChoices):
        INCOME = 'income', 'Entrada'
        EXPENSE = 'expense', 'Saída'

    date = models.DateField('data')
    description = models.CharField('descrição', max_length=180)
    category = models.CharField('categoria', max_length=80)
    kind = models.CharField('tipo', max_length=10, choices=Kind)
    amount = models.DecimalField('valor', max_digits=12, decimal_places=2)
    member = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')

    class Meta:
        ordering = ['-date', '-id']
        verbose_name = 'lançamento'
        verbose_name_plural = 'lançamentos'

    def __str__(self):
        return self.description


class ContactLead(models.Model):
    class Interest(models.TextChoices):
        VISIT = 'visit', 'Planejar visita'
        MINISTRIES = 'ministries', 'Ministérios'
        COUNSELING = 'counseling', 'Aconselhamento'
        EVENTS = 'events', 'Eventos'

    name = models.CharField('nome', max_length=120)
    email = models.EmailField('e-mail')
    whatsapp = models.CharField('WhatsApp', max_length=30)
    interest = models.CharField('interesse', max_length=20, choices=Interest)
    message = models.TextField('mensagem')
    contacted = models.BooleanField('contatado', default=False)
    created_at = models.DateTimeField('recebido em', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'contato'
        verbose_name_plural = 'contatos'

    def __str__(self):
        return f'{self.name} - {self.get_interest_display()}'


class MembershipApplication(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        REVIEW = 'review', 'Em avaliação pastoral'
        COMPLETED = 'completed', 'Concluído'

    candidate_name = models.CharField('nome do candidato', max_length=160)
    candidate_email = models.EmailField('e-mail do candidato')
    form_date = models.DateField('data do formulário', null=True, blank=True)
    status = models.CharField('situação', max_length=20, choices=Status, default=Status.DRAFT)
    responses = models.JSONField('respostas do candidato', default=dict, blank=True)
    pastoral_review = models.JSONField('avaliação pastoral', default=dict, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_membership_applications')
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'candidatura à membresia'
        verbose_name_plural = 'candidaturas à membresia'

    def __str__(self):
        return self.candidate_name


class BibleNote(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bible_notes')
    reference = models.CharField('referência', max_length=80)
    content = models.TextField('anotação', max_length=3000)
    created_at = models.DateTimeField('criada em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizada em', auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'anotação bíblica'
        verbose_name_plural = 'anotações bíblicas'
        constraints = [models.UniqueConstraint(fields=['user', 'reference'], name='unique_bible_note_reference')]


class BibleFavorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bible_favorites')
    reference = models.CharField('referência', max_length=80)
    text = models.TextField('texto', max_length=3000)
    created_at = models.DateTimeField('favoritado em', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'versículo favorito'
        verbose_name_plural = 'versículos favoritos'
        constraints = [models.UniqueConstraint(fields=['user', 'reference'], name='unique_bible_favorite_reference')]

# Create your models here.
