"""
考试业务序列化器
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import ExamRecord, MistakeBook, StudentAnswer
from apps.papers.serializers import PaperSerializer
from apps.papers.models import PaperQuestion
from apps.questions.serializers import QuestionListSerializer, QuestionSerializer


class ExamRecordSerializer(serializers.ModelSerializer):
    """考试记录序列化器"""
    paper = PaperSerializer(read_only=True)
    paper_id = serializers.IntegerField(write_only=True)
    answers = serializers.SerializerMethodField()
    student_name = serializers.CharField(source='student.username', read_only=True)
    score = serializers.SerializerMethodField()  # 直接使用score字段，不再使用_display后缀
    
    class Meta:
        model = ExamRecord
        fields = ['id', 'student', 'student_name', 'paper', 'paper_id',
                 'start_time', 'end_time', 'answers', 'score', 'status',
                 'created_at', 'updated_at']
        read_only_fields = ['id', 'student', 'start_time', 'created_at', 'updated_at']
    
    def get_score(self, obj):
        """获取解密后的总分 - 只有考试结束且评阅完成后才显示"""
        if obj.status != 3 or not obj.is_grading_completed():
            return None
        return obj.get_score()
    
    @extend_schema_field(
        serializers.DictField(
            child=serializers.DictField(
                child=serializers.CharField(allow_null=True),
                allow_null=True
            ),
            allow_empty=True,
        )
    )
    def get_answers(self, obj):
        """获取逐题答案和得分"""
        queryset = StudentAnswer.objects.filter(exam_record=obj).select_related('question')
        ret = {}
        for sa in queryset:
            ret[str(sa.question_id)] = {
                'answer': sa.get_answer(),
                'score': sa.score
            }
        return ret


class PaperQuestionWithAnswerSerializer(serializers.ModelSerializer):
    """试卷题目序列化器（包含答案，用于阅卷）"""
    question = QuestionSerializer(read_only=True)
    
    class Meta:
        model = PaperQuestion
        fields = ['id', 'question', 'score', 'order']


class ExamRecordDetailSerializer(serializers.ModelSerializer):
    """考试记录详情序列化器（用于阅卷）"""
    paper = serializers.SerializerMethodField()
    answers = serializers.SerializerMethodField()
    student_name = serializers.CharField(source='student.username', read_only=True)
    score = serializers.SerializerMethodField()  # 直接使用score字段，不再使用_display后缀

    class Meta:
        model = ExamRecord
        fields = ['id', 'student', 'student_name', 'paper', 'start_time',
                  'end_time', 'answers', 'score', 'status', 'created_at', 'updated_at']
    
    def get_score(self, obj):
        """获取解密后的总分 - 教师端不受状态限制"""
        # 如果是教师，直接显示分数
        if hasattr(self, 'context') and 'request' in self.context:
            user = self.context['request'].user
            if user and hasattr(user, 'role') and user.role == 1:  # 教师
                return obj.get_score()
        
        # 学生端：只有考试结束且评阅完成后才显示
        if obj.status != 3 or not obj.is_grading_completed():
            return None
        return obj.get_score()

    def get_paper(self, obj):
        """获取试卷信息（包含题目和答案）"""
        from apps.papers.serializers import PaperSerializer
        from apps.papers.models import PaperQuestion

        paper_data = PaperSerializer(obj.paper).data

        # 获取试卷题目（包含答案）
        paper_questions = PaperQuestion.objects.filter(paper=obj.paper).select_related('question')
        paper_data['paper_questions'] = PaperQuestionWithAnswerSerializer(paper_questions, many=True).data  # ✅ 修复字段名

        return paper_data

    def get_answers(self, obj):
        """获取逐题答案和得分"""
        queryset = StudentAnswer.objects.filter(exam_record=obj).select_related('question')
        ret = {}
        for sa in queryset:
            ret[str(sa.question_id)] = {
                'answer': sa.get_answer(),
                'score': sa.score
            }
        return ret


class ExamRecordListSerializer(serializers.ModelSerializer):
    """考试记录列表序列化器"""
    paper_title = serializers.CharField(source='paper.title', read_only=True)
    student_name = serializers.SerializerMethodField()
    student_class_name = serializers.CharField(source='student.student_class.name', read_only=True, allow_null=True)
    has_essay_questions = serializers.SerializerMethodField()
    answers = serializers.SerializerMethodField()
    score = serializers.SerializerMethodField()  # 直接使用score字段，不再使用_display后缀
    paper_total_score = serializers.IntegerField(source='paper.total_score', read_only=True)  # 添加试卷总分
    
    class Meta:
        model = ExamRecord
        fields = ['id', 'paper_title', 'student_name', 'student_class_name', 'score', 'paper_total_score', 'status',
                 'start_time', 'end_time', 'created_at', 'has_essay_questions', 'answers']

    def get_student_name(self, obj):
        """优先返回真实姓名，解密失败则回退到用户名"""
        try:
            return obj.student.get_real_name() or obj.student.username
        except Exception:
            return obj.student.username
    
    def get_has_essay_questions(self, obj):
        """判断试卷是否有简答题（需要手动阅卷）"""
        from apps.papers.models import PaperQuestion
        return PaperQuestion.objects.filter(
            paper=obj.paper,
            question__type=4  # 简答题
        ).exists()
    
    def get_score(self, obj):
        """获取解密后的总分 - 教师端不受状态限制"""
        # 如果是教师，直接显示分数
        if hasattr(self, 'context') and 'request' in self.context:
            user = self.context['request'].user
            if user and hasattr(user, 'role') and user.role == 1:  # 教师
                return obj.get_score()
        
        # 如果是学生，只有考试结束且评阅完成后才显示
        if obj.status != 3 or not obj.is_grading_completed():
            return None
        return obj.get_score()
    
    def get_answers(self, obj):
        """获取逐题答案和得分"""
        queryset = StudentAnswer.objects.filter(exam_record=obj).select_related('question')
        ret = {}
        for sa in queryset:
            ret[str(sa.question_id)] = {
                'answer': sa.get_answer(),
                'score': sa.score
            }
        return ret


class ExamResultQuestionSerializer(serializers.ModelSerializer):
    """考试结果题目序列化器"""
    content = serializers.SerializerMethodField()
    options = serializers.SerializerMethodField()
    analysis = serializers.SerializerMethodField()
    type = serializers.IntegerField(source='question.type')

    # 正确答案
    correct_answer = serializers.SerializerMethodField()
    # 学生答案 & 得分
    student_answer = serializers.SerializerMethodField()
    score = serializers.SerializerMethodField()

    class Meta:
        model = StudentAnswer
        fields = [
            'id', 'type', 'content', 'options',
            'correct_answer', 'student_answer', 'analysis', 'score'
        ]

    def get_content(self, obj):
        """获取解密后的题干内容"""
        return obj.question.get_content()
    
    def get_options(self, obj):
        """获取解密后的选项"""
        return obj.question.get_options()
    
    def get_analysis(self, obj):
        """获取解密后的解析"""
        return obj.question.get_analysis()

    def get_correct_answer(self, obj):
        return obj.question.get_answer()

    def get_student_answer(self, obj):
        return obj.get_answer()
    
    def get_score(self, obj):
        return obj.get_score()


class ExamResultSerializer(serializers.ModelSerializer):
    """
    考后复盘 · 考试记录序列化器
    """
    paper_title = serializers.CharField(source='paper.title')
    paper_total_score = serializers.IntegerField(source='paper.total_score')
    status = serializers.IntegerField()
    user_role = serializers.SerializerMethodField()
    score = serializers.SerializerMethodField()  # 直接使用score字段，不再使用_display后缀
    # 逐题明细
    questions = serializers.SerializerMethodField()

    class Meta:
        model = ExamRecord
        fields = [
            'id', 'paper_title', 'paper_total_score',
            'score', 'start_time', 'end_time',
            'status', 'user_role', 'questions'
        ]
    
    def get_score(self, obj):
        """获取解密后的总分 - 只有考试结束且评阅完成后才显示"""
        if obj.status != 3 or not obj.is_grading_completed():
            return None
        score = obj.get_score()
        return score
    
    def get_user_role(self, obj):
        return obj.student.role if hasattr(obj, 'student') and obj.student else None

    def get_questions(self, obj):
        # 学生端：只有考试结束且评阅完成后才能查看作答详情
        if obj.status != 3 or not obj.is_grading_completed():
            return []
        
        answers_qs = StudentAnswer.objects.filter(
            exam_record=obj
        ).select_related('question').order_by('question__id')
        if not answers_qs.exists():
            return []
        result = ExamResultQuestionSerializer(answers_qs, many=True).data
        return result


class MistakeBookSerializer(serializers.ModelSerializer):
    """错题本序列化器

    对外字段保持不变：
    - question: 题目信息
    - user_answer: 学生答案（解密后的可读形式）
    - correct_answer: 正确答案/参考答案（从题目获取）

    内部实现不再依赖错题本表中的明文字段，而是通过 StudentAnswer 与 Question 动态计算。
    """
    question = QuestionListSerializer(read_only=True)
    user_answer = serializers.SerializerMethodField()
    correct_answer = serializers.SerializerMethodField()
    
    class Meta:
        model = MistakeBook
        fields = ['id', 'question', 'user_answer', 'correct_answer', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_user_answer(self, obj):
        """
        通过 student_answer 引用中获取学生答案（解密后）
        """
        if hasattr(obj, 'student_answer') and obj.student_answer:
            try:
                return obj.student_answer.get_answer()
            except Exception:
                pass
        return None

    def get_correct_answer(self, obj):
        """
        统一从 Question 获取正确答案，避免在错题本中重复存储
        """
        question = getattr(obj, 'question', None)
        if question is not None:
            try:
                # Question.get_answer() 已负责解密与 JSON 解析
                return question.get_answer()
            except Exception:
                pass
        return None




