from datetime import date

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import audit
from .balances import month_summary
from .forms import CategoryForm, SettingsForm
from .models import Category, Kind, Movement, TreasurySettings
from .permissions import can_edit_treasury, treasury_edit_required, treasury_view_required
from .rules import BeforeStart, NotConfigured, month_end, month_start, parse_month
from .visibility import description_for


@treasury_view_required
def home(request):
    month = parse_month(request.GET.get('mes'))
    try:
        summary = month_summary(month)
    except NotConfigured:
        if can_edit_treasury(request.user):
            return redirect('tesouraria:settings')
        return render(request, 'tesouraria/not_configured.html')
    except BeforeStart:
        start_month = month_start(TreasurySettings.get().start_date)
        return render(request, 'tesouraria/home.html', {
            'month': month, 'before_start': True,
            'start_month': start_month, 'start_month_param': f'{start_month:%Y-%m}',
        })
    movements = list(Movement.objects.counted()
                     .filter(date__gte=summary.month, date__lte=month_end(summary.month))
                     .select_related('category').order_by('-date', '-id'))
    for movement in movements:
        movement.shown_description = description_for(movement, request.user)
    return render(request, 'tesouraria/home.html', {
        'month': summary.month,
        'summary': summary,
        'movements': movements,
        'prev_param': f'{_shift(summary.month, -1):%Y-%m}',
        'next_param': f'{_shift(summary.month, 1):%Y-%m}',
    })


def _shift(month: date, delta: int) -> date:
    index = month.year * 12 + month.month - 1 + delta
    return date(index // 12, index % 12 + 1, 1)


@treasury_edit_required
def settings(request):
    current = TreasurySettings.get()
    before = audit.snapshot(current) if current else None  # antes do form: is_valid() altera a instância
    form = SettingsForm(request.POST or None, instance=current)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        audit.record(request.user, audit.SETTINGS, saved, 'Abertura registrada',
                     before=before, after=audit.snapshot(saved))
        messages.success(request, 'Abertura da tesouraria salva.')
        return redirect('tesouraria:settings')
    return render(request, 'tesouraria/settings.html', {'form': form, 'locked': SettingsForm.is_locked()})


@treasury_edit_required
def categories(request):
    rows = Category.objects.annotate(uses=Count('movement')).order_by('name')
    return render(request, 'tesouraria/categories.html', {
        'groups': [('Entradas', rows.filter(kind=Kind.INCOME)), ('Saídas', rows.filter(kind=Kind.EXPENSE))],
    })


def _category_form(request, instance, title, verb):
    before = audit.snapshot(instance) if instance else None  # antes do form: is_valid() altera a instância
    form = CategoryForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        audit.record(request.user, audit.CREATE if instance is None else audit.UPDATE, saved,
                     f'Categoria {verb}: {saved.name}', before=before, after=audit.snapshot(saved))
        messages.success(request, f'Categoria {verb}.')
        return redirect('tesouraria:categories')
    return render(request, 'tesouraria/category_form.html', {'form': form, 'title': title})


@treasury_edit_required
def category_create(request):
    return _category_form(request, None, 'Nova categoria', 'criada')


@treasury_edit_required
def category_edit(request, pk):
    return _category_form(request, get_object_or_404(Category, pk=pk), 'Editar categoria', 'alterada')


@treasury_edit_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    before = audit.snapshot(category)
    if category.in_use():
        category.active = False
        category.save(update_fields=['active'])
        audit.record(request.user, audit.ARCHIVE, category, f'Categoria arquivada: {category.name}',
                     before=before, after=audit.snapshot(category))
        messages.success(request, f'A categoria "{category.name}" já tem lançamentos e foi arquivada, '
                                  'não excluída. Ela some das novas escolhas e o histórico continua intacto.')
    else:
        name = category.name
        audit.record(request.user, audit.DELETE, category, f'Categoria excluída: {name}', before=before)
        category.delete()
        messages.success(request, f'Categoria "{name}" excluída.')
    return redirect('tesouraria:categories')


@treasury_edit_required
@require_POST
def category_reactivate(request, pk):
    category = get_object_or_404(Category, pk=pk)
    before = audit.snapshot(category)
    category.active = True
    category.save(update_fields=['active'])
    audit.record(request.user, audit.UPDATE, category, f'Categoria reativada: {category.name}',
                 before=before, after=audit.snapshot(category))
    messages.success(request, f'Categoria "{category.name}" reativada.')
    return redirect('tesouraria:categories')
