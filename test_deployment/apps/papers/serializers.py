"""
试卷序列化器
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import Paper, PaperQuestion
from apps.questions.serializers import QuestionListSerializer


class PaperQuestionSerializer(serializers.ModelSerializer):
    """试卷题目序列化器"""
    question = QuestionListSerializer(read_only=True)
    question_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = PaperQuestion
        fields = ['id', 'question', 'question_id', 'score', 'order']
        read_only_fields = ['id']


class PaperSerializer(serializers.ModelSerializer):
    """试卷序列化器"""
    question_ids = serializers.ListField(
        child=serializers.IntegerField(), 
        write_only=True, 
        required=False,
        allow_empty=False
    )
    paper_questions = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    course_name = serializers.CharField(source='course.name', read_only=True, allow_null=True)
    course_code = serializers.CharField(source='course.code', read_only=True, allow_null=True)
    
    class Meta:
        model = Paper
        fields = ['id', 'title', 'total_score', 'duration', 'question_config',
                 'status', 'course', 'course_name', 'course_code',
                 'created_by', 'created_by_name', 'created_at', 'updated_at',
                 'start_time', 'end_time',
                 'question_ids', 'paper_questions']
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(),
            allow_empty=True,
        )
    )
    def get_paper_questions(self, obj):
        """Get paper question list"""
        questions_qs = obj.paper_questions.all().order_by('order').select_related('question')
        return PaperQuestionSerializer(questions_qs, many=True).data
    
    def create(self, validated_data):
        """创建试卷"""
        question_ids = validated_data.pop('question_ids', [])
        validated_data['created_by'] = self.context['request'].user
        
        # 验证必填字段
        if not validated_data.get('title'):
            raise serializers.ValidationError({'title': '试卷标题不能为空'})
        if not validated_data.get('duration'):
            raise serializers.ValidationError({'duration': '考试时长不能为空'})
        
        paper = Paper.objects.create(**validated_data)
        
        # 创建试卷-题目关联
        if question_ids:
            paper.set_question_ids(question_ids)
            paper.save()
            
            # 计算每道题的分值
            total_score = validated_data.get('total_score', 100)
            score_per_question = total_score / len(question_ids) if question_ids else 0
            
            for idx, qid in enumerate(question_ids):
                PaperQuestion.objects.create(
                    paper=paper,
                    question_id=qid,
                    score=score_per_question,
                    order=idx + 1
                )
        
        return paper
    
    def update(self, instance, validated_data):
        """更新试卷"""
        question_ids = validated_data.pop('question_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if question_ids is not None:
            if not question_ids:
                raise serializers.ValidationError({'question_ids': '题目列表不能为空'})
            
            instance.set_question_ids(question_ids)
            # 更新关联表
            PaperQuestion.objects.filter(paper=instance).delete()
            
            # 计算每道题的分值
            score_per_question = instance.total_score / len(question_ids) if question_ids else 0
            
            for idx, qid in enumerate(question_ids):
                PaperQuestion.objects.create(
                    paper=instance,
                    question_id=qid,
                    score=score_per_question,
                    order=idx + 1
                )
        
        instance.save()
        return instance


class PaperListSerializer(serializers.ModelSerializer):
    """试卷列表序列化器"""
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    course_name = serializers.CharField(source='course.name', read_only=True)
    
    class Meta:
        model = Paper
        fields = ['id', 'title', 'total_score', 'duration', 'status', 
                 'course', 'course_name', 'created_by_name', 'created_at', 'updated_at', 'start_time', 'end_time']


import random

class PaperStudentSerializer(serializers.ModelSerializer):
    """学生试卷序列化器（包含题目但不包含答案）"""
    paper_questions = PaperQuestionSerializer(many=True, read_only=True)
    course_name = serializers.CharField(source='course.name', read_only=True, allow_null=True)
    
    class Meta:
        model = Paper
        fields = ['id', 'title', 'total_score', 'duration', 'status', 
                 'course', 'course_name', 'paper_questions', 'created_at', 'start_time', 'end_time']




