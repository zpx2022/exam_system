"""
试题模型
答案字段使用SM4加密存储
"""
from django.db import models
from django.conf import settings
from utils.gm_crypto import gm_crypto
import json


class Question(models.Model):
    """试题模型"""
    TYPE_CHOICES = [
        (1, '单选题'),
        (2, '多选题'),
        (3, '判断题'),
        (4, '简答题'),
    ]
    
    type = models.SmallIntegerField(choices=TYPE_CHOICES, verbose_name='题型')
    content = models.TextField(verbose_name='题干内容(SM4密文)')
    media_file = models.CharField(max_length=255, blank=True, null=True, verbose_name='媒体文件路径')
    options = models.TextField(blank=True, null=True, verbose_name='选项(SM4密文)')
    answer = models.TextField(verbose_name='答案(SM4密文)')
    analysis = models.TextField(blank=True, null=True, verbose_name='解析(SM4密文)')
    # 试题所属课程（允许为空，兼容已有数据）
    course = models.ForeignKey('courses.Course', on_delete=models.SET_NULL, 
                              null=True, blank=True, related_name='questions', verbose_name='所属课程')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                                   related_name='created_questions', verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'questions_question'
        verbose_name = '试题'
        verbose_name_plural = '试题'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['type'], name='q_type_idx'),
            models.Index(fields=['created_at'], name='q_created_at_idx'),
            models.Index(fields=['created_by', 'created_at'], name='q_creator_crt_idx'),
        ]
    
    def __str__(self):
        # 使用解密后的题干内容显示
        try:
            content = self.get_content()
            return f"{self.get_type_display()} - {content[:50]}"
        except:
            return f"{self.get_type_display()} - [加密题干]"
    
    def save(self, *args, **kwargs):
        """重写save方法，自动加密敏感字段"""
        # 加密content字段
        if self.content and ':' not in self.content:
            self.content = gm_crypto.sm4_encrypt_data(self.content)
        
        # 加密options字段
        if self.options and ':' not in str(self.options):
            if isinstance(self.options, dict):
                options_str = json.dumps(self.options, ensure_ascii=False)
                self.options = gm_crypto.sm4_encrypt_data(options_str)
            else:
                self.options = gm_crypto.sm4_encrypt_data(str(self.options))
        
        # 加密answer字段
        if self.answer and ':' not in str(self.answer):
            if isinstance(self.answer, (dict, list)):
                answer_str = json.dumps(self.answer, ensure_ascii=False)
                self.answer = gm_crypto.sm4_encrypt_data(answer_str)
            else:
                self.answer = gm_crypto.sm4_encrypt_data(str(self.answer))
        
        # 加密analysis字段
        if self.analysis and ':' not in self.analysis:
            self.analysis = gm_crypto.sm4_encrypt_data(str(self.analysis))
        
        super().save(*args, **kwargs)
    
    def set_content(self, content):
        """
        设置题干内容（SM4加密）
        :param content: 题干内容
        """
        self.content = gm_crypto.sm4_encrypt_data(str(content))
    
    def get_content(self):
        """
        获取题干内容（SM4解密）
        :return: 解密后的题干内容
        """
        try:
            return gm_crypto.sm4_decrypt_data(self.content)
        except:
            return self.content  # 如果解密失败，返回原值
    
    def set_options(self, options):
        """
        设置选项（SM4加密）
        :param options: 选项，可以是字典或字符串
        """
        if options is None or options == '':
            self.options = ""
        elif isinstance(options, dict):
            options_str = json.dumps(options, ensure_ascii=False)
            self.options = gm_crypto.sm4_encrypt_data(options_str)
        else:
            self.options = gm_crypto.sm4_encrypt_data(str(options))
    
    def get_options(self):
        """
        获取选项（SM4解密）
        :return: 解密后的选项（字典或字符串）
        """
        if not self.options:
            return {}
        try:
            decrypted = gm_crypto.sm4_decrypt_data(self.options)
            # 尝试解析为JSON
            try:
                return json.loads(decrypted)
            except Exception:
                return decrypted
        except Exception:
            return self.options  # 如果解密失败，返回原值
    
    def set_analysis(self, analysis):
        """
        设置解析（SM4加密）
        :param analysis: 解析内容
        """
        if analysis:
            self.analysis = gm_crypto.sm4_encrypt_data(str(analysis))
        else:
            self.analysis = ""
    
    def get_analysis(self):
        """
        获取解析（SM4解密）
        :return: 解密后的解析内容
        """
        if not self.analysis:
            return ""
        try:
            return gm_crypto.sm4_decrypt_data(self.analysis)
        except:
            return self.analysis  # 如果解密失败，返回原值
    
    def set_answer(self, answer):
        """
        设置答案（SM4加密）
        :param answer: 答案，可以是字符串或字典/列表（会转为JSON）
        """
        if isinstance(answer, (dict, list)):
            answer_str = json.dumps(answer, ensure_ascii=False)
        else:
            answer_str = str(answer)
        
        self.answer = gm_crypto.sm4_encrypt_data(answer_str)
    
    def get_answer(self):
        """
        获取答案（SM4解密）
        :return: 解密后的答案字符串或JSON对象
        """
        try:
            decrypted = gm_crypto.sm4_decrypt_data(self.answer)
            # 尝试解析为JSON
            try:
                answer_data = json.loads(decrypted)
                # 对多选题答案进行排序，与评分逻辑保持一致
                if isinstance(answer_data, list):
                    answer_data = sorted(answer_data)
                return answer_data
            except Exception:
                return decrypted
        except Exception:
            return self.answer  # 如果解密失败，返回原值




