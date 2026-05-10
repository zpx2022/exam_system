"""
班级模型
"""
from django.db import models
from utils.gm_crypto import gm_crypto


class Class(models.Model):
    """班级模型"""
    name = models.CharField(max_length=100, verbose_name='班级名称')
    major = models.CharField(max_length=100, verbose_name='专业')
    institution = models.CharField(max_length=100, verbose_name='所属机构')
    description = models.TextField(blank=True, null=True, verbose_name='班级描述')
    courses = models.ManyToManyField('courses.Course', related_name='classes', blank=True, verbose_name='关联课程')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'classes_class'
        verbose_name = '班级'
        verbose_name_plural = '班级'
        ordering = ['-created_at']
        unique_together = [['name', 'major', 'institution']]
        indexes = [
            models.Index(fields=['major'], name='class_major_idx'),
            models.Index(fields=['institution'], name='class_inst_idx'),
            models.Index(fields=['major', 'institution'], name='class_maj_inst_idx'),
        ]
    
    def save(self, *args, **kwargs):
        """重写save方法，移除description加密"""
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} - {self.major}"
