"""
试题序列化器
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from django.conf import settings
from .models import Question
from apps.courses.models import Course


class QuestionSerializer(serializers.ModelSerializer):
    """试题序列化器"""
    # 直接使用标准字段名，不再使用_display后缀
    content = serializers.CharField(required=False, allow_blank=True)
    options = serializers.JSONField(required=False)
    answer = serializers.CharField(required=False, allow_blank=True)
    analysis = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Question
        fields = ['id', 'type', 'content', 'media_file', 'options', 
                  'answer', 'analysis', 'course', 'created_by',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def validate_content(self, value):
        """Verify question content"""
        if not value or not value.strip():
            raise serializers.ValidationError('Question content cannot be empty')
        return value.strip()
    
    def validate_answer(self, value):
        """Verify answer"""
        # Multiple choice: require non-empty list
        q_type = self.initial_data.get('type') if isinstance(getattr(self, 'initial_data', None), dict) else None
        if q_type == 2:
            if not isinstance(value, list) or len(value) == 0:
                raise serializers.ValidationError('Multiple choice answer cannot be empty')
            return value
        
        # Other question types: require non-empty string (consistent with frontend)
        if isinstance(value, str):
            if not value.strip():
                raise serializers.ValidationError('Answer cannot be empty')
            return value.strip()

        raise serializers.ValidationError('Answer format error')
    
    def to_representation(self, instance):
        """Override representation to decrypt sensitive fields"""
        data = super().to_representation(instance)
        # Decrypt sensitive fields for output
        data['content'] = instance.get_content()
        data['options'] = instance.get_options()
        data['answer'] = instance.get_answer()
        data['analysis'] = instance.get_analysis()
        return data
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_media_file_url(self, obj):
        """Get complete URL of media file"""
        if obj.media_file:
            from django.conf import settings
            return f"{settings.MEDIA_URL.rstrip('/')}/{obj.media_file}"
        return None
    
    def create(self, validated_data):
        """Create question"""
        validated_data['created_by'] = self.context['request'].user
        
        # Get answer from standard field and verify it's not empty
        answer = validated_data.pop('answer', '')
        
        if not answer or (isinstance(answer, str) and not answer.strip()):
            raise serializers.ValidationError({'answer': 'Answer cannot be empty'})
        
        # Extract fields that need encryption and remove from validated_data
        content = validated_data.pop('content', '')
        options = validated_data.pop('options', {})
        analysis = validated_data.pop('analysis', '')
        
        # 先创建对象（不包含加密字段）
        validated_data['answer'] = 'temp'  # 临时值
        validated_data['content'] = ''     # 临时值
        validated_data['options'] = ''     # 临时值
        validated_data['analysis'] = ''    # 临时值
        
        question = Question.objects.create(**validated_data)
        
        # 使用模型的加密方法设置字段
        if content:
            question.set_content(content)
        if options is not None and options != '':
            question.set_options(options)
        if analysis:
            question.set_analysis(analysis)
        # 始终设置answer（已经验证过不为空）
        question.set_answer(answer)
        
        question.save()
        
        return question
    
    def update(self, instance, validated_data):
        """Update question"""
        # Extract fields that need encryption
        content = validated_data.pop('content', None)
        options = validated_data.pop('options', None)
        analysis = validated_data.pop('analysis', None)
        answer = validated_data.pop('answer', None)
        
        # 更新普通字段
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # 使用模型的加密方法更新加密字段
        if content is not None:
            if not content or not content.strip():
                raise serializers.ValidationError({'content': 'Question content cannot be empty'})
            instance.set_content(content)
            
        if options is not None:
            instance.set_options(options)
            
        if analysis is not None:
            instance.set_analysis(analysis)
        
        if answer is not None:
            # Verify answer is not empty
            if not answer or (isinstance(answer, str) and not answer.strip()):
                raise serializers.ValidationError({'answer': 'Answer cannot be empty'})
            
            instance.set_answer(answer)
        
        instance.save()
        return instance


class QuestionListSerializer(serializers.ModelSerializer):
    """试题列表序列化器（不包含答案）"""
    content = serializers.SerializerMethodField()
    options = serializers.SerializerMethodField()
    analysis = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    media_file_url = serializers.SerializerMethodField()
    course_name = serializers.CharField(source='course.name', read_only=True, allow_null=True)
    
    class Meta:
        model = Question
        fields = ['id', 'type', 'content', 'media_file', 'media_file_url', 'options', 
                 'analysis', 'course', 'course_name', 'created_by_name', 'created_at', 'updated_at']
        read_only_fields = ['media_file_url']
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_content(self, obj):
        """获取解密后的题干内容"""
        return obj.get_content()
    
    @extend_schema_field(serializers.JSONField(allow_null=True))
    def get_options(self, obj):
        """获取解密后的选项"""
        return obj.get_options()
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_analysis(self, obj):
        """获取解密后的解析"""
        return obj.get_analysis()
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_media_file_url(self, obj):
        """获取媒体文件的完整URL"""
        if obj.media_file:
            from django.conf import settings
            return f"{settings.MEDIA_URL.rstrip('/')}/{obj.media_file}"
        return None




