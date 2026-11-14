from django.http import HttpResponse
from django.urls import path

from .permissions import treasury_view_required

app_name = 'tesouraria'


@treasury_view_required
def home(request):
    # Provisória: a Task 4 substitui por Caixa do Mês.
    return HttpResponse('Tesouraria')


urlpatterns = [
    path('', home, name='home'),
]
