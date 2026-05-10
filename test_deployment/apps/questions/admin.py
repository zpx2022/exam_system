from django.contrib import admin
from .models import Question


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'type', 'content', 'created_by', 'created_at']
    list_filter = ['type', 'created_at']
    search_fields = ['content']




