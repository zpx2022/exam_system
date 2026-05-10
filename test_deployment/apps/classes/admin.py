"""
班级管理后台
"""
from django.contrib import admin
from .models import Class


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'major', 'institution', 'created_at']
    list_filter = ['created_at', 'institution', 'major']
    search_fields = ['name', 'major', 'institution']
    filter_horizontal = ['courses']
