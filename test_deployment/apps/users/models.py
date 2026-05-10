"""
用户模型
实现分级存储策略：SM3密码+SM4敏感字段
"""
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from utils.gm_crypto import gm_crypto


class UserManager(BaseUserManager):
    """用户管理器"""
    
    def create_user(self, username, password=None, **extra_fields):
        """创建普通用户"""
        if not username:
            raise ValueError('用户名不能为空')
        
        user = self.model(username=username, **extra_fields)
        if password:
            # 使用SM3+Salt加密密码
            password_hash, salt = gm_crypto.sm3_hash_with_salt(password)
            user.password = password_hash
            user.salt = salt
        user.save(using=self._db)
        return user
    
    def create_superuser(self, username, password=None, **extra_fields):
        """创建超级管理员"""
        extra_fields.setdefault('role', 0)
        extra_fields.setdefault('is_active', True)
        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser):
    """用户模型"""
    ROLE_CHOICES = [
        (0, '管理员'),
        (1, '教师'),
        (2, '学生'),
    ]
    
    username = models.CharField(max_length=150, unique=True, verbose_name='用户名')
    password = models.CharField(max_length=128, verbose_name='密码(SM3哈希)')
    salt = models.CharField(max_length=32, verbose_name='动态盐值')
    real_name = models.TextField(verbose_name='真实姓名(SM4密文)')
    phone = models.TextField(blank=True, null=True, verbose_name='手机号(SM4密文)')
    role = models.SmallIntegerField(choices=ROLE_CHOICES, default=2, verbose_name='角色')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name='注册时间')
    # 学生所属班级（仅学生角色使用）
    student_class = models.ForeignKey('classes.Class', on_delete=models.SET_NULL, 
                                     null=True, blank=True, related_name='students', 
                                     verbose_name='所属班级', limit_choices_to={'id__isnull': False})
    
    objects = UserManager()
    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []
    
    class Meta:
        db_table = 'users_user'
        verbose_name = '用户'
        verbose_name_plural = '用户'
        indexes = [
            models.Index(fields=['role'], name='user_role_idx'),
            models.Index(fields=['is_active'], name='user_active_idx'),
            models.Index(fields=['role', 'is_active'], name='user_role_act_idx'),
        ]
    
    def __str__(self):
        return self.username
    
    def set_password(self, raw_password):
        """设置密码（SM3+Salt）"""
        password_hash, salt = gm_crypto.sm3_hash_with_salt(raw_password)
        self.password = password_hash
        self.salt = salt
    
    def check_password(self, raw_password):
        """验证密码"""
        return gm_crypto.verify_password(raw_password, self.password, self.salt)
    
    def save(self, *args, **kwargs):
        """重写save方法，自动加密敏感字段"""
        # 如果real_name不为空且未加密，使用CBC加密
        if self.real_name and ':' not in self.real_name:
            self.real_name = gm_crypto.sm4_encrypt_data(self.real_name)
        
        # 如果phone不为空且未加密，使用CBC加密
        if self.phone is not None and self.phone != '' and ':' not in str(self.phone):
            phone_str = str(self.phone)
            self.phone = gm_crypto.sm4_encrypt_data(phone_str)
        
        super().save(*args, **kwargs)
    
    def set_real_name(self, real_name):
        """设置真实姓名（SM4 CBC加密）"""
        self.real_name = gm_crypto.sm4_encrypt_data(real_name)
    
    def set_phone(self, phone):
        """设置手机号（SM4 CBC加密）"""
        if phone:
            self.phone = gm_crypto.sm4_encrypt_data(phone)
        else:
            self.phone = None
    
    def get_real_name(self):
        """获取真实姓名（SM4 CBC解密）"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            return gm_crypto.sm4_decrypt_data(self.real_name)
        except Exception as e:
            logger.error(f"解密真实姓名失败: {str(e)}")
            return "解密失败"
    
    def get_phone(self):
        """获取手机号（SM4 CBC解密）"""
        if not self.phone:
            return ""
        
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            return gm_crypto.sm4_decrypt_data(self.phone)
        except Exception as e:
            logger.error(f"解密手机号失败: {str(e)}")
            return "解密失败"
    
    @property
    def is_staff(self):
        """是否为管理员"""
        return self.role == 0
    
    @property
    def is_teacher(self):
        """是否为教师"""
        return self.role == 1
    
    @property
    def is_student(self):
        """是否为学生"""
        return self.role == 2




