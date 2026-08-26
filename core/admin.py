from django.contrib import admin

from .models import AccessProfile, Book, ContactLead, Course, CourseEvaluation, Event, Lesson, LessonProgress, Member, Ministry, Transaction


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


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'author_name', 'is_featured', 'is_available', 'sort_order', 'price']
    list_filter = ['is_featured', 'is_available']
    search_fields = ['title', 'subtitle', 'author_name']


admin.site.register([AccessProfile, Ministry, Event, ContactLead, Course, Lesson, LessonProgress, CourseEvaluation])

# Register your models here.
