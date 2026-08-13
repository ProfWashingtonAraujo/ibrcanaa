from django.contrib import admin

from .models import AccessProfile, ContactLead, Event, Member, Ministry, Transaction


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'status', 'ministry_names', 'frequency']
    list_filter = ['status', 'ministries', 'baptized']
    search_fields = ['name', 'email']

    @admin.display(description='ministérios')
    def ministry_names(self, member):
        return ', '.join(member.ministries.values_list('name', flat=True)) or '-'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['date', 'description', 'category', 'kind', 'amount']
    list_filter = ['kind', 'category']


admin.site.register([AccessProfile, Ministry, Event, ContactLead])

# Register your models here.
