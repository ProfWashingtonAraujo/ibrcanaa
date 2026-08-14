from django.contrib import admin

from .models import AccessProfile, ContactLead, Course, CourseEvaluation, Event, Lesson, LessonProgress, Member, Ministry, Transaction


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'status', 'church_entry_date', 'baptism_date', 'ministry_names']
    list_filter = ['status', 'ministries', 'baptism_date', 'church_entry_date']
    search_fields = ['name', 'email']

    @admin.display(description='ministérios')
    def ministry_names(self, member):
        return ', '.join(member.ministries.values_list('name', flat=True)) or '-'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['date', 'description', 'category', 'kind', 'amount']
    list_filter = ['kind', 'category']


admin.site.register([AccessProfile, Ministry, Event, ContactLead, Course, Lesson, LessonProgress, CourseEvaluation])

# Register your models here.
