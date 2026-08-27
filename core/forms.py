from decimal import Decimal
from datetime import date

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, Field, Layout
from dal import autocomplete
from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from .models import AccessProfile, BibleNote, Book, ChurchAboutPage, ChurchHistoryPage, ContactLead, Course, CourseEvaluation, Event, Lesson, Member, MembershipApplication, Ministry, Transaction


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


YES_NO_CHOICES = (('', 'Não informado'), ('yes', 'Sim'), ('no', 'Não'))


class MembershipApplicationForm(forms.Form):
    pastoral_fields = {
        'recommended', 'recommendation_date', 'received_as', 'membership_baptism_date',
        'letter_sent_to', 'received_by', 'pastoral_notes',
    }
    section_definitions = (
        ('Informações pessoais', 'Identificação e contato do candidato.', (
            ('form_date', 'Data do formulário', 'date'), ('candidate_name', 'Nome completo', 'text'),
            ('birth_date', 'Data de nascimento', 'date'), ('address', 'Endereço completo', 'text'),
            ('home_phone', 'Telefone residencial', 'text'), ('mobile_phone', 'Celular', 'text'),
            ('profession', 'Profissão', 'text'), ('education', 'Escolaridade', 'text'),
            ('work_phone', 'Telefone comercial', 'text'), ('candidate_email', 'E-mail', 'email'),
        )),
        ('Família e contexto pessoal', 'Informações familiares e situações que demandam cuidado pastoral.', (
            ('married', 'É casado?', 'yes_no'), ('wedding_date', 'Data de casamento', 'date'),
            ('widowed', 'Já passou por processo de viuvez?', 'yes_no'), ('widow_comments', 'Comentários sobre a viuvez', 'textarea'),
            ('divorced', 'É divorciado?', 'yes_no'), ('divorce_comments', 'Comentários sobre o divórcio', 'textarea'),
            ('married_to_divorced', 'É casado com alguém divorciado?', 'yes_no'),
            ('spouse_divorce_comments', 'Comentários sobre o divórcio do cônjuge', 'textarea'),
            ('child_1_name', 'Nome do filho 1', 'text'), ('child_1_birth_date', 'Nascimento do filho 1', 'date'),
            ('child_2_name', 'Nome do filho 2', 'text'), ('child_2_birth_date', 'Nascimento do filho 2', 'date'),
            ('child_3_name', 'Nome do filho 3', 'text'), ('child_3_birth_date', 'Nascimento do filho 3', 'date'),
            ('child_4_name', 'Nome do filho 4', 'text'), ('child_4_birth_date', 'Nascimento do filho 4', 'date'),
            ('family_composition', 'Composição familiar e com quem reside', 'textarea'),
        )),
        ('Saúde, justiça e cuidado', 'Conteúdo confidencial, acessível somente ao perfil pastoral.', (
            ('legal_process', 'Responde ou já respondeu a processo na justiça?', 'yes_no'),
            ('legal_process_comments', 'Comentários sobre o processo', 'textarea'),
            ('serious_disease', 'Possui doença contagiosa ou grave que precisa comunicar?', 'yes_no'),
            ('serious_disease_comments', 'Cuidados e comentários sobre saúde', 'textarea'),
            ('drug_use', 'Faz ou fez uso de drogas?', 'yes_no'), ('drug_use_comments', 'Comentários sobre uso de drogas', 'textarea'),
            ('psychotropic_or_mental_health', 'Faz ou fez uso de psicotrópicos, ou enfrenta depressão ou alguma síndrome?', 'yes_no'),
            ('psychotropic_comments', 'Cuidados especiais e comentários', 'textarea'),
            ('mental_health_followup', 'Faz acompanhamento com psicólogo ou psiquiatra?', 'yes_no'),
            ('mental_health_comments', 'Comentários sobre acompanhamento', 'textarea'),
            ('possible_tension', 'Existe possível ponto de tensão que precisa comunicar?', 'yes_no'),
            ('possible_tension_comments', 'Comentários sobre o possível ponto de tensão', 'textarea'),
        )),
        ('Conversão e batismo', 'Histórico de fé e aproximação com a igreja.', (
            ('conversion_details', 'Data e lugar da conversão', 'textarea'),
            ('baptism_details', 'Data, lugar e informações do batismo', 'textarea'),
            ('baptism_type', 'Tipo de batismo', 'baptism_type'),
            ('baptism_by_woman', 'O batismo foi realizado por pastora ou mulher?', 'yes_no'),
            ('baptism_neopentecostal', 'O batismo ocorreu em igreja neopentecostal?', 'yes_no'),
            ('church_discovery', 'Como conheceu nossa igreja?', 'textarea'),
            ('attendance_start', 'Como e quando começou a frequentar nossa igreja?', 'textarea'),
            ('new_members_course_date', 'Data de conclusão do curso de novos membros', 'date'),
            ('new_members_course_comments', 'Comentários sobre o curso', 'textarea'),
            ('urgent_spiritual_help', 'Precisa de ajuda espiritual urgente?', 'yes_no'),
            ('urgent_spiritual_help_comments', 'Comentários sobre a necessidade espiritual', 'textarea'),
        )),
        ('Percepção sobre a vida da igreja', 'Impressões do candidato sobre cultos e programações.', (
            ('wednesday_service_comments', 'Culto de quarta-feira à noite', 'textarea'),
            ('sunday_service_comments', 'Culto de domingo à noite', 'textarea'),
            ('sunday_school_comments', 'Escola Bíblica Dominical', 'textarea'),
            ('societies_service_comments', 'Culto de sociedades', 'textarea'),
            ('youth_service_comments', 'Culto de jovens', 'textarea'),
            ('couples_service_comments', 'Culto de casais', 'textarea'),
            ('business_meeting_comments', 'Sessão administrativa', 'textarea'),
            ('program_disagreement', 'Existe algo nas programações com que não concorda ou que incomoda?', 'yes_no'),
            ('program_disagreement_comments', 'Comentários sobre as programações', 'textarea'),
        )),
        ('Serviço, comunhão e doutrina', 'Experiência anterior e compreensão da fé cristã.', (
            ('accepts_pastoral_visit', 'Tem disposição para receber visita pastoral ou de oficiais?', 'yes_no'),
            ('pastoral_visit_comments', 'Comentários sobre visitas', 'textarea'),
            ('previous_discipline', 'Sofreu disciplina na igreja anterior?', 'yes_no'),
            ('previous_discipline_comments', 'Motivo e comentários sobre a disciplina', 'textarea'),
            ('service_interests', 'Em quais áreas da igreja gosta de servir?', 'textarea'),
            ('leadership_experience', 'Já exerceu cargo de liderança em igreja?', 'yes_no'),
            ('leadership_experience_comments', 'Cargo e experiência de liderança', 'textarea'),
            ('demonic_experience', 'Possui experiência pessoal, familiar ou próxima com possessão demoníaca?', 'yes_no'),
            ('demonic_experience_comments', 'Comentários sobre essa experiência', 'textarea'),
            ('gospel_understanding', 'O que é o Evangelho?', 'textarea'),
            ('conversion_understanding', 'O que é conversão?', 'textarea'),
            ('ordinances_understanding', 'Qual o significado do batismo e da ceia?', 'textarea'),
            ('communion_importance', 'Qual a importância da comunhão dos crentes?', 'textarea'),
            ('salvation_loss_belief', 'Acredita que pode perder a salvação? Explique.', 'textarea'),
            ('covenant_signed', 'Assinou o Pacto de Compromisso da igreja?', 'yes_no'),
        )),
        ('Preenchimento pastoral', 'Esta seção deve ser preenchida após entrevista e avaliação pastoral.', (
            ('recommended', 'Candidato recomendado?', 'yes_no'), ('recommendation_date', 'Data da recomendação', 'date'),
            ('received_as', 'Recebido como membro por', 'received_as'),
            ('membership_baptism_date', 'Data do batismo para recebimento', 'date'),
            ('letter_sent_to', 'Carta de transferência enviada a', 'text'),
            ('received_by', 'Recebido por', 'text'), ('pastoral_notes', 'Observações pastorais', 'textarea'),
        )),
    )

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        initial = kwargs.setdefault('initial', {})
        if instance:
            initial.update(instance.responses)
            initial.update(instance.pastoral_review)
            initial.update({
                'candidate_name': instance.candidate_name,
                'candidate_email': instance.candidate_email,
                'form_date': instance.form_date,
                'status': instance.status,
            })
        super().__init__(*args, **kwargs)
        self.fields['status'] = forms.ChoiceField(label='Situação', choices=MembershipApplication.Status)
        for _, _, definitions in self.section_definitions:
            for name, label, kind in definitions:
                self.fields[name] = self._make_field(label, kind, required=name in {'candidate_name', 'candidate_email'})

    @staticmethod
    def _make_field(label, kind, required=False):
        if kind == 'date':
            return forms.DateField(label=label, required=required, widget=forms.DateInput(attrs={'type': 'date'}))
        if kind == 'email':
            return forms.EmailField(label=label, required=required)
        if kind == 'textarea':
            return forms.CharField(label=label, required=required, widget=forms.Textarea(attrs={'rows': 4}))
        if kind == 'yes_no':
            return forms.ChoiceField(label=label, required=False, choices=YES_NO_CHOICES, widget=forms.RadioSelect)
        if kind == 'baptism_type':
            return forms.ChoiceField(label=label, required=False, choices=(('', 'Não informado'), ('sprinkling', 'Aspersão'), ('pouring', 'Efusão'), ('immersion', 'Imersão')), widget=forms.RadioSelect)
        if kind == 'received_as':
            return forms.ChoiceField(label=label, required=False, choices=(('', 'Não informado'), ('baptism', 'Batismo'), ('assembly', 'Assembleia'), ('transfer_letter', 'Carta de transferência')), widget=forms.RadioSelect)
        return forms.CharField(label=label, required=required)

    @property
    def sections(self):
        return [
            (title, description, [self[name] for name, _, _ in definitions])
            for title, description, definitions in self.section_definitions
        ]

    def save(self, created_by):
        application = self.instance or MembershipApplication(created_by=created_by)
        application.candidate_name = self.cleaned_data['candidate_name']
        application.candidate_email = self.cleaned_data['candidate_email']
        application.form_date = self.cleaned_data['form_date']
        application.status = self.cleaned_data['status']
        application.responses = {
            name: value.isoformat() if hasattr(value, 'isoformat') else value
            for name, value in self.cleaned_data.items()
            if name not in self.pastoral_fields | {'candidate_name', 'candidate_email', 'form_date', 'status'}
        }
        application.pastoral_review = {
            name: value.isoformat() if hasattr(value, 'isoformat') else value
            for name, value in self.cleaned_data.items() if name in self.pastoral_fields
        }
        application.save()
        return application


class MembershipCandidateForm(MembershipApplicationForm):
    consent = forms.BooleanField(
        label='Declaro que forneço estas informações voluntariamente e autorizo seu uso exclusivo no processo pastoral de membresia.',
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('status')
        for name in self.pastoral_fields:
            self.fields.pop(name)
        self.fields['consent'] = self.base_fields['consent']

    @property
    def sections(self):
        return [
            (title, description, [self[name] for name, _, _ in definitions])
            for title, description, definitions in self.section_definitions
            if title != 'Preenchimento pastoral'
        ]

    def save(self):
        application = self.instance
        application.candidate_name = self.cleaned_data['candidate_name']
        application.candidate_email = self.cleaned_data['candidate_email']
        application.form_date = self.cleaned_data['form_date']
        application.responses = {
            name: value.isoformat() if hasattr(value, 'isoformat') else value
            for name, value in self.cleaned_data.items()
            if name not in {'candidate_name', 'candidate_email', 'form_date', 'consent'}
        }
        application.status = MembershipApplication.Status.REVIEW
        application.submitted_at = timezone.now()
        application.consented_at = application.submitted_at
        application.save(update_fields=[
            'candidate_name', 'candidate_email', 'form_date', 'responses', 'status',
            'submitted_at', 'consented_at', 'updated_at',
        ])
        return application


class MemberForm(CrispyFormMixin, forms.ModelForm):
    section_definitions = (
        ('Informações pessoais', 'Identificação, contato e dados profissionais.', (
            'name', 'birth_date', 'address', 'email', 'home_phone', 'phone', 'work_phone',
            'profession', 'education',
        )),
        ('Família e estado civil', 'Informações para acompanhamento e cuidado familiar.', (
            'married', 'wedding_date', 'widowed', 'divorced', 'married_to_divorced',
        )),
        ('Filhos', 'Cadastre até quatro filhos e suas datas de nascimento.', (
            'child_1_name', 'child_1_birth_date', 'child_2_name', 'child_2_birth_date',
            'child_3_name', 'child_3_birth_date', 'child_4_name', 'child_4_birth_date',
        )),
        ('Vida na igreja', 'Situação, participação e ministérios do membro.', (
            'ministries', 'status', 'conversion_date', 'baptism_date', 'church_entry_date',
        )),
        ('Acesso ao portal', 'Credenciais e foto usadas na área de membros.', (
            'username', 'photo', 'password1', 'password2',
        )),
    )
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
    full_width_fields = {'address', 'ministries', 'photo', 'username'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

    def clean_ministries(self):
        ministries = self.cleaned_data['ministries']
        if ministries.count() > 3:
            raise ValidationError('Selecione no máximo 3 ministérios.')
        return ministries

    def clean(self):
        cleaned_data = super().clean()
        today = date.today()
        date_fields = [
            'birth_date', 'wedding_date', 'conversion_date', 'baptism_date', 'church_entry_date',
        ] + [f'child_{index}_birth_date' for index in range(1, 5)]
        for field_name in date_fields:
            value = cleaned_data.get(field_name)
            if value and value > today:
                self.add_error(field_name, 'A data não pode estar no futuro.')
        birth_date = cleaned_data.get('birth_date')
        wedding_date = cleaned_data.get('wedding_date')
        if birth_date and wedding_date and wedding_date < birth_date:
            self.add_error('wedding_date', 'A data de casamento não pode ser anterior ao nascimento.')
        for field_name in ['conversion_date', 'baptism_date', 'church_entry_date']:
            value = cleaned_data.get(field_name)
            if birth_date and value and value < birth_date:
                self.add_error(field_name, 'A data não pode ser anterior ao nascimento.')
        conversion_date = cleaned_data.get('conversion_date')
        baptism_date = cleaned_data.get('baptism_date')
        if conversion_date and baptism_date and baptism_date < conversion_date:
            self.add_error('baptism_date', 'A data de batismo não pode ser anterior à conversão.')
        for index in range(1, 5):
            name_field = f'child_{index}_name'
            birth_field = f'child_{index}_birth_date'
            if cleaned_data.get(birth_field) and not cleaned_data.get(name_field):
                self.add_error(name_field, 'Informe o nome do filho associado a esta data.')
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

    @property
    def sections(self):
        return [
            (title, description, [self[name] for name in field_names])
            for title, description, field_names in self.section_definitions
        ]

    def save(self, commit=True):
        member = super().save(commit=False)
        if member.baptism_date:
            member.baptized = True
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
        fields = [
            'name', 'birth_date', 'address', 'email', 'home_phone', 'phone', 'work_phone',
            'profession', 'education', 'married', 'wedding_date', 'widowed', 'divorced',
            'married_to_divorced',
            'child_1_name', 'child_1_birth_date', 'child_2_name', 'child_2_birth_date',
            'child_3_name', 'child_3_birth_date', 'child_4_name', 'child_4_birth_date',
            'ministries', 'status', 'conversion_date', 'baptism_date', 'church_entry_date',
        ]
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'wedding_date': forms.DateInput(attrs={'type': 'date'}),
            'child_1_birth_date': forms.DateInput(attrs={'type': 'date'}),
            'child_2_birth_date': forms.DateInput(attrs={'type': 'date'}),
            'child_3_birth_date': forms.DateInput(attrs={'type': 'date'}),
            'child_4_birth_date': forms.DateInput(attrs={'type': 'date'}),
            'conversion_date': forms.DateInput(attrs={'type': 'date'}),
            'baptism_date': forms.DateInput(attrs={'type': 'date'}),
            'church_entry_date': forms.DateInput(attrs={'type': 'date'}),
            'married': forms.RadioSelect(choices=((None, 'Não informado'), (True, 'Sim'), (False, 'Não'))),
            'widowed': forms.RadioSelect(choices=((None, 'Não informado'), (True, 'Sim'), (False, 'Não'))),
            'divorced': forms.RadioSelect(choices=((None, 'Não informado'), (True, 'Sim'), (False, 'Não'))),
            'married_to_divorced': forms.RadioSelect(choices=((None, 'Não informado'), (True, 'Sim'), (False, 'Não'))),
            'ministries': forms.CheckboxSelectMultiple,
        }


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
    full_width_fields = {'description'}

    class Meta:
        model = Ministry
        fields = ['name', 'leader_name', 'description', 'status']
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Apresente o propósito e as atividades do ministério.',
            }),
        }


class ChurchAboutPageForm(CrispyFormMixin, forms.ModelForm):
    full_width_fields = {'intro', 'highlight_1_text', 'highlight_2_text', 'highlight_3_text'}

    class Meta:
        model = ChurchAboutPage
        fields = [
            'eyebrow', 'heading', 'intro',
            'highlight_1_title', 'highlight_1_text',
            'highlight_2_title', 'highlight_2_text',
            'highlight_3_title', 'highlight_3_text',
        ]
        widgets = {
            'intro': forms.Textarea(attrs={'rows': 4}),
            'highlight_1_text': forms.Textarea(attrs={'rows': 3}),
            'highlight_2_text': forms.Textarea(attrs={'rows': 3}),
            'highlight_3_text': forms.Textarea(attrs={'rows': 3}),
        }


class ChurchHistoryPageForm(CrispyFormMixin, forms.ModelForm):
    full_width_fields = {'intro', 'photo_1_url', 'photo_2_url', 'photo_3_url', 'milestone_1_text', 'milestone_2_text', 'milestone_3_text'}

    class Meta:
        model = ChurchHistoryPage
        fields = [
            'eyebrow', 'heading', 'intro', 'photo_1_url', 'photo_2_url', 'photo_3_url',
            'milestone_1_title', 'milestone_1_text',
            'milestone_2_title', 'milestone_2_text',
            'milestone_3_title', 'milestone_3_text',
        ]
        widgets = {
            'intro': forms.Textarea(attrs={'rows': 4}),
            'photo_1_url': forms.URLInput(attrs={'placeholder': 'https://...'}),
            'photo_2_url': forms.URLInput(attrs={'placeholder': 'https://...'}),
            'photo_3_url': forms.URLInput(attrs={'placeholder': 'https://...'}),
            'milestone_1_text': forms.Textarea(attrs={'rows': 3}),
            'milestone_2_text': forms.Textarea(attrs={'rows': 3}),
            'milestone_3_text': forms.Textarea(attrs={'rows': 3}),
        }


class BookForm(CrispyFormMixin, forms.ModelForm):
    full_width_fields = {'description', 'cover_url', 'purchase_url', 'preview_url'}

    class Meta:
        model = Book
        fields = ['title', 'subtitle', 'author_name', 'description', 'cover_url', 'purchase_url', 'preview_url', 'price', 'is_featured', 'is_available', 'sort_order']
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Resumo curto do livro para a vitrine pública.',
            }),
            'cover_url': forms.URLInput(attrs={'placeholder': 'https://...'}),
            'purchase_url': forms.URLInput(attrs={'placeholder': 'Link de compra ou WhatsApp'}),
            'preview_url': forms.URLInput(attrs={'placeholder': 'Link para amostra ou leitura'}),
        }


class CourseForm(CrispyFormMixin, forms.ModelForm):
    full_width_fields = {'title', 'description', 'cover_url', 'published'}

    class Meta:
        model = Course
        fields = ['title', 'description', 'instructor', 'cover_url', 'published']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Apresente o conteúdo e os objetivos do curso.'}),
            'cover_url': forms.URLInput(attrs={'placeholder': 'https://...'}),
        }


class LessonForm(CrispyFormMixin, forms.ModelForm):
    full_width_fields = {'title', 'youtube_url', 'description'}

    def __init__(self, *args, course=None, **kwargs):
        self.course = course
        super().__init__(*args, **kwargs)

    def clean_position(self):
        position = self.cleaned_data['position']
        lessons = Lesson.objects.filter(course=self.course, position=position)
        if self.instance.pk:
            lessons = lessons.exclude(pk=self.instance.pk)
        if lessons.exists():
            raise ValidationError('Já existe uma aula nesta ordem.')
        return position

    class Meta:
        model = Lesson
        fields = ['title', 'youtube_url', 'position', 'description']
        widgets = {
            'youtube_url': forms.URLInput(attrs={'placeholder': 'https://www.youtube.com/watch?v=...'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class CourseEvaluationForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        label='Como você avalia este curso?',
        choices=((5, 'Excelente'), (4, 'Muito bom'), (3, 'Bom'), (2, 'Regular'), (1, 'Precisa melhorar')),
        coerce=int,
        widget=forms.RadioSelect,
    )

    class Meta:
        model = CourseEvaluation
        fields = ['rating', 'learning', 'feedback']
        widgets = {
            'learning': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Conte o que mais marcou sua caminhada.'}),
            'feedback': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Opcional'}),
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
        self.fields['member'].queryset = available_members

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
                selected_member.name = user.get_full_name()
                selected_member.save(update_fields=['user', 'name'])
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
