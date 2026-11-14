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
    path('a-confirmar/', views.pending, name='pending'),
    path('a-confirmar/<int:pk>/confirmar/', views.pending_confirm, name='pending_confirm'),
    path('a-confirmar/<int:pk>/recusar/', views.pending_reject, name='pending_reject'),
    path('contas/', views.payables, name='payables'),
    path('contas/nova/', views.payable_create, name='payable_create'),
    path('contas/<int:pk>/editar/', views.payable_edit, name='payable_edit'),
    path('contas/<int:pk>/pagar/', views.payable_pay, name='payable_pay'),
    path('contas/<int:pk>/desfazer/', views.payable_undo, name='payable_undo'),
    path('contas/<int:pk>/cancelar/', views.payable_cancel, name='payable_cancel'),
    path('recorrentes/', views.recurring_list, name='recurring'),
    path('recorrentes/nova/', views.recurring_create, name='recurring_create'),
    path('recorrentes/<int:pk>/editar/', views.recurring_edit, name='recurring_edit'),
    path('recorrentes/<int:pk>/alternar/', views.recurring_toggle, name='recurring_toggle'),
    path('conferencia/', views.cash_count, name='cash_count'),
    path('fechamento/', views.month_close, name='month_close'),
    path('fechamento/reabrir/', views.month_reopen, name='month_reopen'),
    path('parecer/', views.opinion, name='opinion'),
    path('ofertas-especiais/', views.special, name='special'),
    path('relatorio/', views.report, name='report'),
    path('relatorio/pdf/', views.report_pdf, name='report_pdf'),
    path('dizimistas/', views.tithers, name='tithers'),
    path('historico/', views.audit_log, name='audit'),
    path('historico-anterior/', views.legacy, name='legacy'),
    path('categorias/', views.categories, name='categories'),
    path('categorias/nova/', views.category_create, name='category_create'),
    path('categorias/<int:pk>/editar/', views.category_edit, name='category_edit'),
    path('categorias/<int:pk>/excluir/', views.category_delete, name='category_delete'),
    path('categorias/<int:pk>/reativar/', views.category_reactivate, name='category_reactivate'),
]
