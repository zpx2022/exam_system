"""
课程模型
"""
from django.db import models
from django.conf import settings
from utils.gm_crypto import gm_crypto


class Course(models.Model):
    """课程模型"""
    name = models.CharField(max_length=100, verbose_name='课程名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='课程代码')
    description = models.TextField(blank=True, null=True, verbose_name='课程描述')
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                null=True, related_name='taught_courses', verbose_name='授课教师')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'courses_course'
        verbose_name = '课程'
        verbose_name_plural = '课程'
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        """重写save方法，移除description加密"""
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.code} - {self.name}"



