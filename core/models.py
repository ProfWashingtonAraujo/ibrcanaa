import re
import uuid
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone


def membership_link_expiry():
    return timezone.now() + timedelta(days=14)


def youtube_video_id(url):
    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return None
    host = (parsed.hostname or '').lower().removeprefix('www.')
    video_id = None
    if host == 'youtu.be':
        video_id = parsed.path.strip('/').split('/')[0]
    elif host in {'youtube.com', 'm.youtube.com', 'music.youtube.com'}:
        path_parts = parsed.path.strip('/').split('/')
        if parsed.path == '/watch':
            video_id = parse_qs(parsed.query).get('v', [None])[0]
        elif path_parts and path_parts[0] in {'embed', 'shorts', 'live'} and len(path_parts) > 1:
            video_id = path_parts[1]
    return video_id if video_id and re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id) else None


def validate_youtube_url(value):
    if not youtube_video_id(value):
        raise ValidationError('Informe uma URL válida de vídeo do YouTube.')


class AccessProfile(models.Model):
    class Role(models.TextChoices):
        PASTOR = 'pastor', 'Pastor'
        BOARD = 'board', 'Admin'
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


class Book(models.Model):
    title = models.CharField('título', max_length=140)
    subtitle = models.CharField('subtítulo', max_length=180, blank=True)
    author_name = models.CharField('autor', max_length=120, default='Pr. Washington Araujo')
    description = models.TextField('descrição', blank=True)
    cover_url = models.URLField('capa', blank=True)
    purchase_url = models.URLField('link de compra', blank=True)
    preview_url = models.URLField('link de leitura', blank=True)
    price = models.DecimalField('preço', max_digits=10, decimal_places=2, null=True, blank=True)
    is_featured = models.BooleanField('em destaque', default=False)
    is_available = models.BooleanField('disponível', default=True)
    sort_order = models.PositiveSmallIntegerField('ordem', default=0)

    class Meta:
        ordering = ['sort_order', 'title']
        verbose_name = 'livro'
        verbose_name_plural = 'livros'

    def __str__(self):
        return self.title


class Member(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Ativo'
        LEADERSHIP = 'leadership', 'Liderança'
        VISITOR = 'visitor', 'Visitante'
        NEW = 'new', 'Novo'
        AWAY = 'away', 'Afastado'

    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='member_profile')
    name = models.CharField('nome', max_length=120)
    birth_date = models.DateField('data de nascimento', null=True, blank=True)
    address = models.CharField('endereço completo', max_length=255, blank=True)
    email = models.EmailField('e-mail', unique=True)
    home_phone = models.CharField('telefone residencial', max_length=30, blank=True)
    phone = models.CharField('celular', max_length=30, blank=True)
    work_phone = models.CharField('telefone comercial', max_length=30, blank=True)
    profession = models.CharField('profissão', max_length=120, blank=True)
    education = models.CharField('escolaridade', max_length=120, blank=True)
    married = models.BooleanField('casado', null=True, blank=True)
    wedding_date = models.DateField('data de casamento', null=True, blank=True)
    widowed = models.BooleanField('já passou por processo de viuvez', null=True, blank=True)
    divorced = models.BooleanField('divorciado', null=True, blank=True)
    married_to_divorced = models.BooleanField('casado com alguém divorciado', null=True, blank=True)
    child_1_name = models.CharField('nome do filho 1', max_length=120, blank=True)
    child_1_birth_date = models.DateField('nascimento do filho 1', null=True, blank=True)
    child_2_name = models.CharField('nome do filho 2', max_length=120, blank=True)
    child_2_birth_date = models.DateField('nascimento do filho 2', null=True, blank=True)
    child_3_name = models.CharField('nome do filho 3', max_length=120, blank=True)
    child_3_birth_date = models.DateField('nascimento do filho 3', null=True, blank=True)
    child_4_name = models.CharField('nome do filho 4', max_length=120, blank=True)
    child_4_birth_date = models.DateField('nascimento do filho 4', null=True, blank=True)
    ministries = models.ManyToManyField(Ministry, blank=True, related_name='members', verbose_name='ministérios')
    status = models.CharField('status', max_length=20, choices=Status, default=Status.ACTIVE)
    conversion_date = models.DateField('data de conversão', null=True, blank=True)
    baptism_date = models.DateField('data de batismo', null=True, blank=True)
    church_entry_date = models.DateField('data de entrada na igreja', null=True, blank=True)
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

    @staticmethod
    def _duration_since(start_date):
        if not start_date:
            return 'Não informado'
        today = timezone.localdate()
        months = (today.year - start_date.year) * 12 + today.month - start_date.month
        if today.day < start_date.day:
            months -= 1
        years, remaining_months = divmod(max(0, months), 12)
        parts = []
        if years:
            parts.append(f'{years} ano' if years == 1 else f'{years} anos')
        if remaining_months:
            parts.append(f'{remaining_months} mês' if remaining_months == 1 else f'{remaining_months} meses')
        return ' e '.join(parts) if parts else 'Menos de 1 mês'

    @property
    def converted_duration(self):
        return self._duration_since(self.conversion_date)

    @property
    def church_duration(self):
        return self._duration_since(self.church_entry_date)


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
    access_token = models.UUIDField('token de acesso', default=uuid.uuid4, unique=True, editable=False)
    link_expires_at = models.DateTimeField('link válido até', default=membership_link_expiry)
    link_revoked_at = models.DateTimeField('link revogado em', null=True, blank=True)
    submitted_at = models.DateTimeField('enviado pelo candidato em', null=True, blank=True)
    consented_at = models.DateTimeField('consentimento registrado em', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_membership_applications')
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'candidatura à membresia'
        verbose_name_plural = 'candidaturas à membresia'

    def __str__(self):
        return self.candidate_name

    @property
    def link_is_available(self):
        return not self.link_revoked_at and not self.submitted_at and self.link_expires_at > timezone.now()


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


class Course(models.Model):
    title = models.CharField('título', max_length=160)
    description = models.TextField('descrição', max_length=2000)
    instructor = models.CharField('instrutor', max_length=120, blank=True)
    cover_url = models.URLField('URL da capa', blank=True, help_text='Opcional. Use uma imagem horizontal.')
    published = models.BooleanField('publicado para os membros', default=False)
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'curso'
        verbose_name_plural = 'cursos'

    def __str__(self):
        return self.title

    @property
    def cover_image_url(self):
        cover_video_id = youtube_video_id(self.cover_url)
        if cover_video_id:
            return f'https://i.ytimg.com/vi/{cover_video_id}/hqdefault.jpg'
        if self.cover_url:
            return self.cover_url
        first_lesson = self.lessons.first()
        return first_lesson.thumbnail_url if first_lesson else ''


class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lessons', verbose_name='curso')
    title = models.CharField('título', max_length=160)
    description = models.TextField('descrição', max_length=2000, blank=True)
    youtube_url = models.URLField('URL do vídeo no YouTube', validators=[validate_youtube_url])
    position = models.PositiveSmallIntegerField('ordem', default=1)

    class Meta:
        ordering = ['position', 'id']
        verbose_name = 'aula'
        verbose_name_plural = 'aulas'
        constraints = [models.UniqueConstraint(fields=['course', 'position'], name='unique_course_lesson_position')]

    def __str__(self):
        return f'{self.course} - {self.title}'

    @property
    def youtube_id(self):
        return youtube_video_id(self.youtube_url)

    @property
    def embed_url(self):
        return f'https://www.youtube-nocookie.com/embed/{self.youtube_id}'

    @property
    def thumbnail_url(self):
        return f'https://i.ytimg.com/vi/{self.youtube_id}/hqdefault.jpg'


class LessonProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progress_records')
    completed_at = models.DateTimeField('concluída em', auto_now_add=True)

    class Meta:
        verbose_name = 'progresso de aula'
        verbose_name_plural = 'progressos de aulas'
        constraints = [models.UniqueConstraint(fields=['user', 'lesson'], name='unique_user_lesson_progress')]


class CourseEvaluation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='course_evaluations')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='evaluations')
    rating = models.PositiveSmallIntegerField('nota')
    learning = models.TextField('principal aprendizado', max_length=2000)
    feedback = models.TextField('comentários e sugestões', max_length=2000, blank=True)
    certificate_id = models.UUIDField('código do certificado', default=uuid.uuid4, unique=True, editable=False)
    completed_at = models.DateTimeField('concluído em', auto_now_add=True)

    class Meta:
        ordering = ['-completed_at']
        verbose_name = 'avaliação de curso'
        verbose_name_plural = 'avaliações de cursos'
        constraints = [models.UniqueConstraint(fields=['user', 'course'], name='unique_user_course_evaluation')]

# Create your models here.
