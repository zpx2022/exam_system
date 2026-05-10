"""
班级模型的序列化器
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import Class
from apps.courses.models import Course


class ClassSerializer(serializers.ModelSerializer):
    """班级序列化器"""
    # courses字段用于在创建/更新时接收课程ID列表
    # many=True表示这是一个多对多关系
    # write_only=True表示这个字段只用于写入（创建/更新），不会在读取时返回
    courses = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Course.objects.all(),
        write_only=True,
        required=False  # 允许创建班级时不关联任何课程
    )

    # course_details用于在读取时返回详细的课程信息，而不是仅仅ID
    course_details = serializers.SerializerMethodField()
    # student_count用于返回该班级的学生数量
    student_count = serializers.SerializerMethodField()

    class Meta:
        model = Class
        fields = ['id', 'name', 'major', 'institution', 'description', 'created_at', 'updated_at', 'courses', 'course_details', 'student_count']
        read_only_fields = ['id', 'created_at', 'updated_at', 'course_details', 'student_count']
        extra_kwargs = {
            'name': {'required': False},
            'major': {'required': False},
            'institution': {'required': False},
        }

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(),
            allow_empty=True,
        )
    )
    def get_course_details(self, obj):
        """获取与班级关联的课程的详细信息"""
        # 使用prefetch_related('courses')可以优化性能
        courses = obj.courses.all()
        return [{'id': course.id, 'name': course.name, 'code': course.code} for course in courses]
    
    @extend_schema_field(serializers.IntegerField())
    def get_student_count(self, obj):
        """获取该班级的学生数量"""
        # 如果queryset使用了annotate，直接使用student_count属性
        # 否则使用students.count()（会有N+1查询问题，但作为后备方案）
        return getattr(obj, 'student_count', obj.students.count())

    def create(self, validated_data):
        """创建班级并处理课程关联"""
        courses_data = validated_data.pop('courses', [])
        class_instance = Class.objects.create(**validated_data)
        if courses_data:
            class_instance.courses.set(courses_data)
        return class_instance

    def update(self, instance, validated_data):
        """更新班级并处理课程关联"""
        courses_data = validated_data.pop('courses', None)
        
        # 如果只更新courses字段（部分更新），直接更新关联关系
        if courses_data is not None and len(validated_data) == 0:
            instance.courses.set(courses_data)
            instance.save()  # 触发 updated_at 更新
            return instance
        
        # 更新班级实例的其他字段
        # 如果 validated_data 为空，说明是部分更新且只更新了 courses，已经在上面处理了
        if validated_data:
            instance = super().update(instance, validated_data)

        # 如果请求中包含了courses字段，则更新关联
        if courses_data is not None:
            instance.courses.set(courses_data)
            
        return instance
