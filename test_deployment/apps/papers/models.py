"""
试卷模型
"""
from django.db import models
from django.conf import settings
import json


class Paper(models.Model):
    """试卷模型"""

    class Status(models.IntegerChoices):
        DRAFT = 0, '草稿'
        PUBLISHED = 1, '已发布'

    title = models.CharField(max_length=100, verbose_name='试卷标题')
    total_score = models.IntegerField(default=100, verbose_name='总分')
    duration = models.IntegerField(verbose_name='考试时长(分钟)')
    question_config = models.JSONField(default=dict, verbose_name='题目配置(JSON)')
    status = models.SmallIntegerField(choices=Status.choices, default=Status.DRAFT, verbose_name='状态')
    # 试卷所属课程（允许为空，兼容已有数据）
    course = models.ForeignKey('courses.Course', on_delete=models.SET_NULL, 
                              null=True, blank=True, related_name='papers', verbose_name='所属课程')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name='created_papers', verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    start_time = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    target_classes = models.ManyToManyField('classes.Class', related_name='papers_to_take', blank=True, verbose_name='指定班级')
    
    class Meta:
        db_table = 'papers_paper'
        verbose_name = '试卷'
        verbose_name_plural = '试卷'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status'], name='paper_status_idx'),
            models.Index(fields=['created_at'], name='paper_crt_at_idx'),
            models.Index(fields=['status', 'created_at'], name='paper_st_crt_idx'),
            models.Index(fields=['created_by', 'created_at'], name='paper_cr_crt_idx'),
        ]
    
    def __str__(self):
        return self.title
    
    def get_question_ids(self):
        """获取题目ID列表"""
        if isinstance(self.question_config, dict):
            return self.question_config.get('question_ids', [])
        elif isinstance(self.question_config, list):
            return self.question_config
        return []
    
    def set_question_ids(self, question_ids):
        """设置题目ID列表"""
        self.question_config = {'question_ids': question_ids}


class PaperQuestion(models.Model):
    """试卷-题目关联表"""
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='paper_questions')
    question = models.ForeignKey('questions.Question', on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='分值')
    order = models.IntegerField(default=0, verbose_name='排序')
    
    class Meta:
        db_table = 'papers_paperquestion'
        verbose_name = '试卷题目'
        verbose_name_plural = '试卷题目'
        unique_together = ['paper', 'question']
        ordering = ['order']
        indexes = [
            models.Index(fields=['paper', 'order'], name='pq_paper_order_idx'),
        ]




