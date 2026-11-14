from datetime import date

from django.shortcuts import redirect, render

from .balances import month_summary
from .models import Movement, TreasurySettings
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
def settings_placeholder(request):
    # Provisória: a Task 5 substitui por o formulário de abertura.
    return render(request, 'tesouraria/settings_placeholder.html')
