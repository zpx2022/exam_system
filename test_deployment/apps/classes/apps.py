"""
班级应用配置
"""
from django.apps import AppConfig


class ClassesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.classes'
    verbose_name = '班级管理'
