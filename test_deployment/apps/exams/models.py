"""
考试业务模型
学生答案使用SM4加密存储
"""
from django.db import models
from django.conf import settings
from utils.gm_crypto import gm_crypto
import json


class StudentAnswer(models.Model):
    """学生单题作答记录模型"""
    exam_record = models.ForeignKey('ExamRecord', on_delete=models.CASCADE, related_name='answers', verbose_name='考试记录')
    question = models.ForeignKey('questions.Question', on_delete=models.CASCADE, verbose_name='题目')
    answer = models.TextField(verbose_name='学生答案(SM4密文)')
    score = models.TextField(blank=True, null=True, verbose_name='得分(SM4密文)')

    class Meta:
        db_table = 'exams_studentanswer'
        unique_together = ['exam_record', 'question']
        verbose_name = '学生答案'
        verbose_name_plural = '学生答案'
    
    def save(self, *args, **kwargs):
        """重写save方法，自动加密敏感字段"""
        # 加密answer字段
        if self.answer and ':' not in self.answer:
            if isinstance(self.answer, (dict, list)):
                answer_str = json.dumps(self.answer, ensure_ascii=False)
                self.answer = gm_crypto.sm4_encrypt_data(answer_str)
            else:
                self.answer = gm_crypto.sm4_encrypt_data(str(self.answer))
        
        # 加密score字段
        if self.score and ':' not in str(self.score):
            self.score = gm_crypto.sm4_encrypt_data(str(self.score))
        
        super().save(*args, **kwargs)
    
    def set_answer(self, answer_data):
        """设置答案（SM4 CBC加密）"""
        answer_str = json.dumps(answer_data, ensure_ascii=False)
        self.answer = gm_crypto.sm4_encrypt_data(answer_str)

    def get_answer(self):
        """获取答案（SM4 CBC解密）"""
        try:
            decrypted = gm_crypto.sm4_decrypt_data(self.answer)
            answer_data = json.loads(decrypted)
            
            # 对多选题答案进行排序，与评分逻辑保持一致
            if isinstance(answer_data, list):
                answer_data = sorted(answer_data)
            
            return answer_data
        except:
            return {} # 或进行适当的错误处理
    
    def set_score(self, score):
        """设置得分（SM4 CBC加密）"""
        if score is not None:
            self.score = gm_crypto.sm4_encrypt_data(str(score))
        else:
            self.score = ""
    
    def get_score(self):
        """获取得分（SM4 CBC解密）"""
        if not self.score:
            return None
        try:
            decrypted = gm_crypto.sm4_decrypt_data(self.score)
            return float(decrypted)
        except:
            return None

class ExamRecord(models.Model):
    """考试记录模型"""

    class Status(models.IntegerChoices):
        IN_PROGRESS = 0, '进行中'
        GRADING = 1, '批改中'  # 等待时间窗口或教师阅卷
        TEACHER_GRADED = 2, '教师已阅卷'  # 教师已完成阅卷，等待时间窗口结束
        COMPLETED = 3, '已完成'  # 可查看成绩（时间窗口结束+阅卷完成）
    
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name='exam_records', verbose_name='学生')
    paper = models.ForeignKey('papers.Paper', on_delete=models.CASCADE,
                             related_name='exam_records', verbose_name='试卷')
    start_time = models.DateTimeField(auto_now_add=True, verbose_name='开始时间')
    end_time = models.DateTimeField(blank=True, null=True, verbose_name='结束时间')
    student_answers = models.TextField(blank=True, null=True, verbose_name='学生答案(SM4密文)')
    score = models.TextField(blank=True, null=True, verbose_name='得分(SM4密文)')
    status = models.SmallIntegerField(choices=Status.choices, default=Status.IN_PROGRESS, verbose_name='状态')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'exams_examrecord'
        verbose_name = '考试记录'
        verbose_name_plural = '考试记录'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status'], name='er_status_idx'),
            models.Index(fields=['student', 'status'], name='er_stu_st_idx'),
            models.Index(fields=['paper', 'status'], name='er_paper_st_idx'),
            models.Index(fields=['student', 'created_at'], name='er_stu_crt_idx'),
            models.Index(fields=['paper', 'created_at'], name='er_paper_crt_idx'),
        ]
    
    def save(self, *args, **kwargs):
        """重写save方法，自动加密敏感字段"""
        # 加密student_answers字段
        if self.student_answers and ':' not in self.student_answers:
            if isinstance(self.student_answers, dict):
                answers_str = json.dumps(self.student_answers, ensure_ascii=False)
                self.student_answers = gm_crypto.sm4_encrypt_data(answers_str)
            else:
                self.student_answers = gm_crypto.sm4_encrypt_data(str(self.student_answers))
        
        # 加密score字段
        if self.score and ':' not in self.score:
            self.score = gm_crypto.sm4_encrypt_data(str(self.score))
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.student.username} - {self.paper.title}"
    
    def set_student_answers(self, answers):
        """
        设置学生答案（SM4 CBC加密）
        :param answers: 答案字典，格式：{question_id: answer}
        """
        answers_str = json.dumps(answers, ensure_ascii=False)
        self.student_answers = gm_crypto.sm4_encrypt_data(answers_str)
    
    def get_student_answers(self):
        """
        获取学生答案（SM4 CBC解密）
        :return: 答案字典
        """
        if not self.student_answers:
            return {}
        
        try:
            decrypted = gm_crypto.sm4_decrypt_data(self.student_answers)
            return json.loads(decrypted)
        except:
            return {}
    
    # 保持向后兼容的别名
    def set_user_answers(self, answers):
        """向后兼容的别名"""
        return self.set_student_answers(answers)
    
    def get_user_answers(self):
        """向后兼容的别名"""
        return self.get_student_answers()
    
    def set_score(self, score):
        """设置得分（SM4 CBC加密）"""
        if score is not None:
            self.score = gm_crypto.sm4_encrypt_data(str(score))
        else:
            self.score = ""
    
    def get_score(self):
        """获取得分（SM4 CBC解密）"""
        if not self.score:
            return None
        try:
            decrypted = gm_crypto.sm4_decrypt_data(self.score)
            return float(decrypted)
        except:
            return None

    def is_grading_completed(self):
        """检查评阅是否完成"""
        # 检查是否有未评分的主观题（简答题）
        from apps.questions.models import Question
        from apps.papers.models import PaperQuestion
        
        # 获取试卷中的所有主观题
        subjective_questions = PaperQuestion.objects.filter(
            paper=self.paper,
            question__type=4  # 简答题
        ).values_list('question_id', flat=True)
        
        if not subjective_questions:
            # 如果没有主观题，评阅自动完成
            return True
        
        # 检查这些主观题是否都有分数
        unanswered_count = StudentAnswer.objects.filter(
            exam_record=self,
            question_id__in=subjective_questions,
            score__in=['', None]  # 分数为空
        ).count()
        
        return unanswered_count == 0


class MistakeBook(models.Model):
    """错题本模型"""
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name='mistakes', verbose_name='学生')
    question = models.ForeignKey('questions.Question', on_delete=models.CASCADE,
                                related_name='mistakes', verbose_name='题目')
    exam_record = models.ForeignKey(ExamRecord, on_delete=models.CASCADE,
                                   related_name='mistakes', verbose_name='考试记录')
    # 为了安全起见，不再在错题本中存储明文答案，而是通过引用获取
    # student_answer 关联到原始学生作答记录（其中答案字段已使用 SM4 加密）
    student_answer = models.ForeignKey(
        'StudentAnswer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mistake_entries',
        verbose_name='学生答案记录引用'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='记录时间')
    
    class Meta:
        db_table = 'exams_mistakebook'
        verbose_name = '错题本'
        verbose_name_plural = '错题本'
        unique_together = ['student', 'question', 'exam_record']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'created_at'], name='mb_stu_crt_idx'),
        ]
    
    def __str__(self):
        return f"{self.student.username} - {self.question.id}"




