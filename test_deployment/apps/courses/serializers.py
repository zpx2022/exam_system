"""
课程序列化器
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import Course


class CourseSerializer(serializers.ModelSerializer):
    """课程序列化器"""
    teacher_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = ['id', 'name', 'code', 'description', 'teacher', 'teacher_name', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
    
    def validate_name(self, value):
        """验证课程名称"""
        if not value or not value.strip():
            raise serializers.ValidationError('课程名称不能为空')
        return value.strip()
    
    def validate_code(self, value):
        """验证课程代码"""
        if not value or not value.strip():
            raise serializers.ValidationError('课程代码不能为空')
        return value.strip()
    
    def get_teacher_name(self, obj):
        """获取教师姓名"""
        if obj.teacher:
            return obj.teacher.get_real_name()
        return None
