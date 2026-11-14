from django.urls import path

from . import views

app_name = 'tesouraria'

urlpatterns = [
    path('', views.home, name='home'),
    path('configuracoes/', views.settings, name='settings'),
    path('categorias/', views.categories, name='categories'),
    path('categorias/nova/', views.category_create, name='category_create'),
    path('categorias/<int:pk>/editar/', views.category_edit, name='category_edit'),
    path('categorias/<int:pk>/excluir/', views.category_delete, name='category_delete'),
    path('categorias/<int:pk>/reativar/', views.category_reactivate, name='category_reactivate'),
]
