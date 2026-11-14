from django.urls import path

from . import views

app_name = 'tesouraria'

urlpatterns = [
    path('', views.home, name='home'),
    path('configuracoes/', views.settings_placeholder, name='settings'),
]
