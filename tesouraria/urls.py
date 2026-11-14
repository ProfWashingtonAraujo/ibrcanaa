from django.urls import path

from . import views

app_name = 'tesouraria'

urlpatterns = [
    path('', views.home, name='home'),
    path('configuracoes/', views.settings, name='settings'),
    path('lancamentos/', views.movements, name='movements'),
    path('lancamentos/novo/', views.movement_create, name='movement_create'),
    path('lancamentos/<int:pk>/editar/', views.movement_edit, name='movement_edit'),
    path('lancamentos/<int:pk>/excluir/', views.movement_delete, name='movement_delete'),
    path('depositos/novo/', views.transfer_create, name='transfer_create'),
    path('depositos/<int:pk>/excluir/', views.transfer_delete, name='transfer_delete'),
    path('categorias/', views.categories, name='categories'),
    path('categorias/nova/', views.category_create, name='category_create'),
    path('categorias/<int:pk>/editar/', views.category_edit, name='category_edit'),
    path('categorias/<int:pk>/excluir/', views.category_delete, name='category_delete'),
    path('categorias/<int:pk>/reativar/', views.category_reactivate, name='category_reactivate'),
]
