from django.contrib import admin
from .models import Paper, PaperQuestion


@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'total_score', 'duration', 'status', 'created_by', 'created_at']
    list_filter = ['status', 'created_at']


@admin.register(PaperQuestion)
class PaperQuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'paper', 'question', 'score', 'order']




