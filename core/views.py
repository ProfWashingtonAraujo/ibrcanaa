from decimal import Decimal
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from dal import autocomplete

from .bible import BIBLE_BOOKS, fetch_chapter, get_book, get_daily_verse
from .charts import attendance_chart, finance_composition_chart, reports_chart, weekly_cashflow_chart
from .forms import BibleNoteForm, ContactLeadForm, EventForm, LoginForm, MemberContributionForm, MemberForm, MembershipApplicationForm, MembershipCandidateForm, MinistryForm, TransactionForm, UserAccountForm
from .models import AccessProfile, BibleFavorite, BibleNote, ContactLead, Event, Member, MembershipApplication, Ministry, Transaction


EVENT_COLORS = ('#173984', '#2752b3', '#d09b31', '#3b7a68', '#7957a8')


def staff_required(view):
    return user_passes_test(lambda user: user.is_authenticated and user.is_staff, login_url='login')(view)


def user_manager_required(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        can_manage = request.user.is_superuser or AccessProfile.objects.filter(
            user=request.user,
            role__in=AccessProfile.USER_MANAGER_ROLES,
        ).exists()
        if not can_manage:
            return HttpResponseForbidden('Apenas Pastor e Diretoria podem gerenciar usuários.')
        return view(request, *args, **kwargs)

    return wrapped


def pastor_required(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        is_pastor = AccessProfile.objects.filter(
            user=request.user,
            role=AccessProfile.Role.PASTOR,
        ).exists()
        if not is_pastor:
            return HttpResponseForbidden('Conteúdo confidencial restrito ao perfil Pastor.')
        return view(request, *args, **kwargs)
    return wrapped


def financial_access_required(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        role = AccessProfile.objects.filter(user=request.user).values_list('role', flat=True).first()
        if not request.user.is_staff or role == AccessProfile.Role.PASTOR:
            return HttpResponseForbidden('O perfil Pastor não possui acesso à área financeira.')
        return view(request, *args, **kwargs)
    return wrapped


class MemberAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        can_manage = self.request.user.is_authenticated and (
            self.request.user.is_superuser
            or AccessProfile.objects.filter(
                user=self.request.user,
                role__in=AccessProfile.USER_MANAGER_ROLES,
            ).exists()
        )
        if not can_manage:
            return Member.objects.none()
        queryset = Member.objects.select_related('user').filter(user__isnull=True)
        if self.q:
            queryset = queryset.filter(Q(name__icontains=self.q) | Q(email__icontains=self.q))
        return queryset


def home(request):
    from swingtime.models import Occurrence

    form = ContactLeadForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('contact_thanks')
    next_occurrence = Occurrence.objects.select_related('event', 'event__church_event').filter(
        start_time__gte=timezone.now(),
        event__church_event__isnull=False,
    ).first()
    return render(request, 'core/home.html', {
        'form': form,
        'next_occurrence': next_occurrence,
        'public_ministries': Ministry.objects.all(),
        'daily_verse': get_daily_verse(timezone.localdate()),
    })


def public_ministry_feed(request):
    response = JsonResponse([
        {
            'name': ministry.name,
            'description': ministry.description,
            'status': ministry.status,
            'statusLabel': ministry.get_status_display(),
        }
        for ministry in Ministry.objects.all()
    ], safe=False)
    if request.headers.get('Origin') == 'https://profwashingtonaraujo.github.io':
        response['Access-Control-Allow-Origin'] = 'https://profwashingtonaraujo.github.io'
    return response


def public_daily_verse(request):
    response = JsonResponse(get_daily_verse(timezone.localdate()))
    if request.headers.get('Origin') == 'https://profwashingtonaraujo.github.io':
        response['Access-Control-Allow-Origin'] = 'https://profwashingtonaraujo.github.io'
    response['Cache-Control'] = 'public, max-age=3600'
    return response


def public_event_feed(request):
    from swingtime.models import Occurrence

    try:
        range_start = timezone.datetime.fromisoformat(request.GET['start'])
        range_end = timezone.datetime.fromisoformat(request.GET['end'])
    except (KeyError, ValueError):
        return JsonResponse({'error': 'Período inválido.'}, status=400)

    occurrences = Occurrence.objects.select_related('event', 'event__church_event').filter(
        start_time__lt=range_end,
        end_time__gt=range_start,
        event__church_event__isnull=False,
    )
    kinds = list(Event.objects.order_by('kind').values_list('kind', flat=True).distinct())
    colors = {name: EVENT_COLORS[index % len(EVENT_COLORS)] for index, name in enumerate(kinds)}
    return JsonResponse([
        {
            'id': str(occurrence.pk),
            'title': occurrence.event.title,
            'start': occurrence.start_time.isoformat(),
            'end': occurrence.end_time.isoformat(),
            'backgroundColor': colors.get(occurrence.event.church_event.kind, EVENT_COLORS[0]),
            'borderColor': colors.get(occurrence.event.church_event.kind, EVENT_COLORS[0]),
            'extendedProps': {
                'kind': occurrence.event.church_event.kind,
                'location': occurrence.event.church_event.location,
                'description': occurrence.event.church_event.description or 'Programação da comunidade.',
            },
        }
        for occurrence in occurrences
    ], safe=False)


def contact_thanks(request):
    return render(request, 'core/contact_thanks.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard' if request.user.is_staff else 'member_portal')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        return redirect('dashboard' if user.is_staff else 'member_portal')
    return render(request, 'core/login.html', {'form': form})


@login_required
def logout_view(request):
    if request.method == 'POST':
        logout(request)
        return redirect('home')
    return HttpResponseForbidden('Use POST para sair.')


def dashboard_context(user=None):
    active_statuses = [Member.Status.ACTIVE, Member.Status.LEADERSHIP]
    members = Member.objects.prefetch_related('ministries')
    show_finances = not user or not AccessProfile.objects.filter(
        user=user, role=AccessProfile.Role.PASTOR,
    ).exists()
    context = {
        'member_count': members.count(),
        'active_count': members.filter(status__in=active_statuses).count(),
        'visitor_count': members.filter(status__in=[Member.Status.VISITOR, Member.Status.NEW]).count(),
        'average_frequency': round(members.aggregate(avg=Avg('frequency'))['avg'] or 0),
        'event_count': Event.objects.count(),
        'show_finances': show_finances,
        'upcoming_events': Event.objects.filter(starts_at__gte=timezone.now())[:4],
    }
    if show_finances:
        transactions = Transaction.objects.all()
        income = transactions.filter(kind=Transaction.Kind.INCOME).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        expense = transactions.filter(kind=Transaction.Kind.EXPENSE).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        context.update({'income': income, 'expense': expense, 'balance': income - expense})
    return context


@staff_required
def dashboard(request):
    context = dashboard_context(request.user)
    context['recent_members'] = Member.objects.prefetch_related('ministries')[:5]
    context['attendance_chart'] = attendance_chart(Member.objects.all())
    return render(request, 'core/dashboard.html', context)


@staff_required
def members(request):
    context = dashboard_context(request.user)
    members_query = Member.objects.prefetch_related('ministries')
    search = request.GET.get('q', '').strip()
    selected_status = request.GET.get('status', '').strip()
    selected_ministry = request.GET.get('ministry', '').strip()
    if search:
        members_query = members_query.filter(
            Q(name__icontains=search) | Q(email__icontains=search) | Q(phone__icontains=search)
        )
    if selected_status:
        members_query = members_query.filter(status=selected_status)
    if selected_ministry.isdigit():
        members_query = members_query.filter(ministries__id=selected_ministry)

    context.update({
        'members': Paginator(members_query, 12).get_page(request.GET.get('page')),
        'filtered_count': members_query.count(),
        'search': search,
        'selected_status': selected_status,
        'selected_ministry': selected_ministry,
        'status_choices': Member.Status.choices,
        'ministries': Ministry.objects.all(),
        'baptized_count': Member.objects.filter(baptized=True).count(),
        'care_count': Member.objects.filter(frequency__lt=60).count(),
    })
    return render(request, 'core/members.html', context)


@staff_required
@transaction.atomic
def member_form(request, pk=None):
    instance = get_object_or_404(Member, pk=pk) if pk else None
    form = MemberForm(request.POST or None, request.FILES or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Membro salvo com sucesso.')
        return redirect('members')
    return render(request, 'core/entity_form.html', {'form': form, 'title': 'Editar membro' if instance else 'Novo membro', 'back_url': 'members'})


@staff_required
def ministries(request):
    search = request.GET.get('q', '').strip()
    selected_status = request.GET.get('status', '').strip()
    ministries_query = Ministry.objects.annotate(member_count=Count('members'))
    if search:
        ministries_query = ministries_query.filter(
            Q(name__icontains=search) | Q(leader_name__icontains=search)
        )
    if selected_status:
        ministries_query = ministries_query.filter(status=selected_status)
    return render(request, 'core/ministries.html', {
        'ministries': ministries_query,
        'filtered_count': ministries_query.count(),
        'active_count': Ministry.objects.filter(status=Ministry.Status.ACTIVE).count(),
        'recruiting_count': Ministry.objects.filter(status=Ministry.Status.RECRUITING).count(),
        'member_total': Member.objects.filter(ministries__isnull=False).distinct().count(),
        'search': search,
        'selected_status': selected_status,
        'status_choices': Ministry.Status.choices,
    })


@staff_required
def ministry_form(request, pk=None):
    instance = get_object_or_404(Ministry, pk=pk) if pk else None
    form = MinistryForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Ministério salvo com sucesso.')
        return redirect('ministries')
    return render(request, 'core/entity_form.html', {
        'form': form,
        'title': 'Editar ministério' if instance else 'Novo ministério',
        'back_url': 'ministries',
    })


@pastor_required
def membership_applications(request):
    search = request.GET.get('q', '').strip()
    applications = MembershipApplication.objects.select_related('created_by')
    if search:
        applications = applications.filter(
            Q(candidate_name__icontains=search) | Q(candidate_email__icontains=search)
        )
    return render(request, 'core/membership_applications.html', {
        'applications': applications,
        'search': search,
    })


@pastor_required
def membership_application_form(request, pk=None):
    instance = get_object_or_404(MembershipApplication, pk=pk) if pk else None
    form = MembershipApplicationForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        form.save(request.user)
        messages.success(request, 'Questionário de membresia salvo com segurança.')
        return redirect('membership_applications')
    return render(request, 'core/membership_application_form.html', {
        'form': form,
        'application': instance,
        'candidate_link': request.build_absolute_uri(
            reverse('membership_candidate_form', args=[instance.access_token])
        ) if instance else '',
    })


@pastor_required
def membership_application_link_action(request, pk, action):
    application = get_object_or_404(MembershipApplication, pk=pk)
    if request.method != 'POST':
        return HttpResponseForbidden('Use POST para alterar o link.')
    if action == 'renew':
        import uuid
        application.access_token = uuid.uuid4()
        application.link_expires_at = timezone.now() + timedelta(days=14)
        application.link_revoked_at = None
        application.submitted_at = None
        application.consented_at = None
        application.status = MembershipApplication.Status.DRAFT
        application.save(update_fields=[
            'access_token', 'link_expires_at', 'link_revoked_at', 'submitted_at',
            'consented_at', 'status', 'updated_at',
        ])
        messages.success(request, 'Novo link gerado com validade de 14 dias.')
    elif action == 'revoke':
        application.link_revoked_at = timezone.now()
        application.save(update_fields=['link_revoked_at', 'updated_at'])
        messages.success(request, 'Link de preenchimento revogado.')
    else:
        return HttpResponseForbidden('Ação inválida.')
    return redirect('membership_application_edit', pk=application.pk)


@transaction.atomic
def membership_candidate_form(request, token):
    applications = MembershipApplication.objects.select_for_update() if request.method == 'POST' else MembershipApplication.objects
    application = get_object_or_404(applications, access_token=token)
    if application.submitted_at:
        response = render(request, 'core/membership_candidate_unavailable.html', {
            'title': 'Questionário já enviado',
            'message': 'Suas respostas já foram recebidas. Entre em contato com a igreja se precisar de ajuda.',
        })
        response['Cache-Control'] = 'no-store'
        return response
    if application.link_revoked_at or application.link_expires_at <= timezone.now():
        response = render(request, 'core/membership_candidate_unavailable.html', {
            'title': 'Link indisponível',
            'message': 'Este link expirou ou foi revogado. Solicite um novo link ao responsável pastoral.',
        }, status=410)
        response['Cache-Control'] = 'no-store'
        return response
    form = MembershipCandidateForm(request.POST or None, instance=application)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('membership_candidate_thanks')
    response = render(request, 'core/membership_candidate_form.html', {
        'form': form,
        'application': application,
    })
    response['Cache-Control'] = 'no-store'
    return response


def membership_candidate_thanks(request):
    return render(request, 'core/membership_candidate_thanks.html')


@staff_required
def ministry_delete(request, pk):
    ministry = get_object_or_404(Ministry, pk=pk)
    if request.method != 'POST':
        return HttpResponseForbidden('Use POST para excluir.')
    ministry.delete()
    messages.success(request, 'Ministério excluído com sucesso.')
    return redirect('ministries')


@staff_required
def events(request):
    return render(request, 'core/events.html', {
        'event_kinds': Event.objects.order_by('kind').values_list('kind', flat=True).distinct(),
        **dashboard_context(request.user),
    })


@staff_required
def event_feed(request):
    from swingtime.models import Occurrence

    try:
        range_start = timezone.datetime.fromisoformat(request.GET['start'])
        range_end = timezone.datetime.fromisoformat(request.GET['end'])
    except (KeyError, ValueError):
        return JsonResponse({'error': 'Período inválido.'}, status=400)

    kind = request.GET.get('kind', '').strip()
    occurrences = Occurrence.objects.select_related('event', 'event__church_event').filter(
        start_time__lt=range_end,
        end_time__gt=range_start,
        event__church_event__isnull=False,
    )
    if kind:
        occurrences = occurrences.filter(event__church_event__kind=kind)

    kinds = list(Event.objects.order_by('kind').values_list('kind', flat=True).distinct())
    colors = {name: EVENT_COLORS[index % len(EVENT_COLORS)] for index, name in enumerate(kinds)}
    payload = []
    for occurrence in occurrences:
        church_event = occurrence.event.church_event
        payload.append({
            'id': str(occurrence.pk),
            'title': occurrence.event.title,
            'start': occurrence.start_time.isoformat(),
            'end': occurrence.end_time.isoformat(),
            'backgroundColor': colors.get(church_event.kind, EVENT_COLORS[0]),
            'borderColor': colors.get(church_event.kind, EVENT_COLORS[0]),
            'extendedProps': {
                'churchEventId': church_event.pk,
                'kind': church_event.kind,
                'location': church_event.location,
                'description': church_event.description or 'Programação da comunidade.',
                'expectedAttendance': church_event.expected_attendance,
            },
        })
    return JsonResponse(payload, safe=False)


@staff_required
def event_form(request, pk=None):
    instance = get_object_or_404(Event, pk=pk) if pk else None
    form = EventForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        event = form.save()
        sync_calendar_event(event)
        messages.success(request, 'Evento salvo com sucesso.')
        return redirect('events')
    return render(request, 'core/entity_form.html', {
        'form': form,
        'title': 'Editar evento' if instance else 'Novo evento',
        'back_url': 'events',
    })


@staff_required
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if request.method != 'POST':
        return HttpResponseForbidden('Use POST para excluir.')
    calendar_event = event.calendar_event
    event.delete()
    if calendar_event:
        calendar_event.delete()
    messages.success(request, 'Evento excluído com sucesso.')
    return redirect('events')


def sync_calendar_event(event):
    from swingtime.models import Event as CalendarEvent, EventType, Occurrence

    event.refresh_from_db()
    event_type = EventType.objects.filter(label=event.kind[:50]).first()
    if event_type is None:
        base = ''.join(character for character in event.kind.lower() if character.isalnum())[:4] or 'evt'
        abbreviation = base
        counter = 1
        while EventType.objects.filter(abbr=abbreviation).exists():
            suffix = str(counter)
            abbreviation = f'{base[:4 - len(suffix)]}{suffix}'
            counter += 1
        event_type = EventType.objects.create(abbr=abbreviation, label=event.kind[:50])
    calendar_event = event.calendar_event or CalendarEvent()
    calendar_event.title = event.title
    calendar_event.description = event.description
    calendar_event.event_type = event_type
    calendar_event.save()
    calendar_event.occurrence_set.all().delete()
    Occurrence.objects.create(
        event=calendar_event,
        start_time=event.starts_at,
        end_time=event.starts_at + timedelta(hours=2),
    )
    if event.calendar_event_id != calendar_event.pk:
        event.calendar_event = calendar_event
        event.save(update_fields=['calendar_event'])


@financial_access_required
def finance(request):
    context = dashboard_context(request.user)
    transactions = Transaction.objects.select_related('member')
    category_totals = transactions.values('category').annotate(total=Sum('amount')).order_by('-total')
    context.update({
        'transactions': transactions,
        'category_totals': category_totals,
        'finance_chart': finance_composition_chart(context['income'], context['expense']),
        'cashflow_chart': weekly_cashflow_chart(transactions),
    })
    return render(request, 'core/finance.html', context)


@financial_access_required
def transaction_form(request):
    form = TransactionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Lançamento registrado com sucesso.')
        return redirect('finance')
    return render(request, 'core/entity_form.html', {'form': form, 'title': 'Novo lançamento', 'back_url': 'finance'})


@staff_required
def reports(request):
    context = dashboard_context(request.user)
    context['ministries'] = Ministry.objects.annotate(member_count=Count('members'))
    context['contacts_pending'] = ContactLead.objects.filter(contacted=False).count()
    context['reports_chart'] = reports_chart(Member.objects.all())
    return render(request, 'core/reports.html', context)


@user_manager_required
def user_accounts(request):
    search = request.GET.get('q', '').strip()
    selected_role = request.GET.get('role', '').strip()
    users = User.objects.select_related('access_profile', 'member_profile').order_by('first_name', 'username')
    if search:
        users = users.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(username__icontains=search)
            | Q(email__icontains=search)
        )
    if selected_role:
        users = users.filter(access_profile__role=selected_role)
    context = {
        'users': Paginator(users, 15).get_page(request.GET.get('page')),
        'filtered_count': users.count(),
        'search': search,
        'selected_role': selected_role,
        'role_choices': AccessProfile.Role.choices,
        'active_users': User.objects.filter(is_active=True).count(),
        'admin_users': AccessProfile.objects.filter(role__in=AccessProfile.ADMIN_ROLES).count(),
    }
    return render(request, 'core/user_accounts.html', context)


@user_manager_required
@transaction.atomic
def user_account_form(request, pk=None):
    instance = get_object_or_404(User, pk=pk) if pk else None
    form = UserAccountForm(request.POST or None, request.FILES or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        if instance == request.user and not form.cleaned_data['is_active']:
            form.add_error('is_active', 'Você não pode desativar sua própria conta.')
        elif instance == request.user and form.cleaned_data['role'] not in AccessProfile.USER_MANAGER_ROLES:
            form.add_error('role', 'Você não pode remover sua própria permissão de gestão.')
        else:
            form.save()
            messages.success(request, 'Usuário salvo com sucesso.')
            return redirect('user_accounts')
    return render(request, 'core/entity_form.html', {
        'form': form,
        'title': 'Editar usuário' if instance else 'Novo usuário',
        'back_url': 'user_accounts',
    })


@user_manager_required
@transaction.atomic
def user_account_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method != 'POST':
        return HttpResponseForbidden('Use POST para excluir.')
    if user == request.user:
        messages.error(request, 'Você não pode excluir sua própria conta.')
    elif user.is_superuser:
        messages.error(request, 'Uma conta de superusuário não pode ser excluída por esta tela.')
    else:
        user.delete()
        messages.success(request, 'Usuário excluído com sucesso.')
    return redirect('user_accounts')


@login_required
@transaction.atomic
def member_portal(request):
    try:
        member = request.user.member_profile
    except Member.DoesNotExist:
        if request.user.is_staff:
            return redirect('dashboard')
        return HttpResponseForbidden('Este usuário não possui perfil de membro.')
    contribution_form = MemberContributionForm(request.POST or None)
    if request.method == 'POST' and contribution_form.is_valid():
        category = contribution_form.cleaned_data['category']
        note = contribution_form.cleaned_data['note']
        description = f'{category[:-1]} via portal - {member.name}'
        if note:
            description = f'{description}: {note}'
        Transaction.objects.create(
            date=timezone.localdate(),
            description=description,
            category=category,
            kind=Transaction.Kind.INCOME,
            amount=contribution_form.cleaned_data['amount'],
            member=member,
        )
        messages.success(request, 'Contribuição registrada com sucesso. Obrigado!')
        return redirect('member_portal')

    contributions = member.transactions.filter(kind=Transaction.Kind.INCOME)
    upcoming = Event.objects.filter(starts_at__gte=timezone.now())[:4]
    contribution_total = contributions.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    first_name = member.name.split()[0]
    return render(request, 'core/member_portal.html', {
        'member': member,
        'first_name': first_name,
        'contributions': contributions[:5],
        'contribution_total': contribution_total,
        'contribution_count': contributions.count(),
        'contribution_form': contribution_form,
        'upcoming_events': upcoming,
        'next_event': upcoming.first(),
    })


@login_required
def bible_reader(request):
    book = get_book(request.GET.get('livro', 'joao')) or get_book('joao')
    try:
        chapter_number = int(request.GET.get('capitulo', 3))
    except (TypeError, ValueError):
        chapter_number = 1
    chapter_number = min(max(chapter_number, 1), book[2])
    chapter = fetch_chapter(book[1], chapter_number)
    reference = f'{book[1]} {chapter_number}'
    note = BibleNote.objects.filter(user=request.user, reference=reference).first()
    return render(request, 'core/bible_reader.html', {
        'books': BIBLE_BOOKS,
        'selected_book': book,
        'chapter_number': chapter_number,
        'chapter_numbers': range(1, book[2] + 1),
        'chapter': chapter,
        'previous_chapter': chapter_number - 1 if chapter_number > 1 else None,
        'next_chapter': chapter_number + 1 if chapter_number < book[2] else None,
        'note_form': BibleNoteForm(instance=note),
        'recent_notes': request.user.bible_notes.all()[:4],
        'recent_favorites': request.user.bible_favorites.all()[:5],
    })


@login_required
@transaction.atomic
def bible_note_save(request):
    if request.method != 'POST':
        return HttpResponseForbidden('Use POST para salvar.')
    book = get_book(request.POST.get('book', ''))
    try:
        chapter_number = int(request.POST.get('chapter', 0))
    except (TypeError, ValueError):
        chapter_number = 0
    if not book or not 1 <= chapter_number <= book[2]:
        return HttpResponseForbidden('Referência inválida.')
    reference = f'{book[1]} {chapter_number}'
    note = BibleNote.objects.filter(user=request.user, reference=reference).first()
    form = BibleNoteForm(request.POST, instance=note)
    if form.is_valid():
        saved_note = form.save(commit=False)
        saved_note.user = request.user
        saved_note.reference = reference
        saved_note.save()
        messages.success(request, 'Anotação salva na sua jornada.')
    else:
        messages.error(request, 'Não foi possível salvar a anotação.')
    return redirect(f"{reverse('bible_reader')}?livro={book[0]}&capitulo={chapter_number}#anotacao")


@login_required
@transaction.atomic
def bible_favorite_toggle(request):
    if request.method != 'POST':
        return HttpResponseForbidden('Use POST para favoritar.')
    book = get_book(request.POST.get('book', ''))
    try:
        chapter_number = int(request.POST.get('chapter', 0))
        verse_number = int(request.POST.get('verse', 0))
    except (TypeError, ValueError):
        return HttpResponseForbidden('Referência inválida.')
    if not book or not 1 <= chapter_number <= book[2] or verse_number < 1:
        return HttpResponseForbidden('Referência inválida.')
    chapter = fetch_chapter(book[1], chapter_number)
    verse = next((item for item in (chapter or {}).get('verses', []) if item['verse'] == verse_number), None)
    if not verse:
        return HttpResponseForbidden('Versículo não encontrado.')
    reference = f'{book[1]} {chapter_number}:{verse_number}'
    favorite, created = BibleFavorite.objects.get_or_create(
        user=request.user,
        reference=reference,
        defaults={'text': verse['text'].strip()},
    )
    if not created:
        favorite.delete()
    return redirect(f"{reverse('bible_reader')}?livro={book[0]}&capitulo={chapter_number}#v{verse_number}")

# Create your views here.
