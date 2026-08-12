from django.contrib import admin

from .models import AccessProfile, ContactLead, Event, Member, Ministry, Transaction


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'status', 'ministry', 'frequency']
    list_filter = ['status', 'ministry', 'baptized']
    search_fields = ['name', 'email']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['date', 'description', 'category', 'kind', 'amount']
    list_filter = ['kind', 'category']


admin.site.register([AccessProfile, Ministry, Event, ContactLead])

# Register your models here.
