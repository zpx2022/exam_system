from django.contrib import admin
from .models import ExamRecord, MistakeBook


@admin.register(ExamRecord)
class ExamRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'student', 'paper', 'score', 'status', 'start_time', 'end_time']
    list_filter = ['status', 'start_time']


@admin.register(MistakeBook)
class MistakeBookAdmin(admin.ModelAdmin):
    list_display = ['id', 'student', 'question', 'exam_record', 'created_at']




