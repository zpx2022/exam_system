"""
试卷管理视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from utils.permissions import IsTeacher
from .models import Paper, PaperQuestion
from .serializers import PaperSerializer, PaperListSerializer, PaperStudentSerializer
from apps.questions.models import Question
import random
from collections import defaultdict
from django.db.models import Avg, Count


class PaperViewSet(viewsets.ModelViewSet):
    """试卷视图集"""
    def get_queryset(self):
        """过滤查询集"""
        queryset = Paper.objects.all()
        
        # Students can only see published papers
        if self.request.user and self.request.user.role == 2:
            queryset = queryset.filter(status=1)  # Only published papers
        # Teachers can see their own papers
        elif self.request.user and self.request.user.role == 1:
            queryset = queryset.filter(created_by=self.request.user)
        
        return queryset
    
    permission_classes = [IsAuthenticated, IsTeacher]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PaperListSerializer
        return PaperSerializer
    
    def get_permissions(self):
        if self.action == 'student_papers':
            return [IsAuthenticated()]
        elif self.action in ['list', 'retrieve']:
            # Allow students to view published papers for exam purposes
            if self.request.user and self.request.user.role == 2:
                return [IsAuthenticated()]
        return super().get_permissions()
    
    def retrieve(self, request, *args, **kwargs):
        """获取试卷详情"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'code': 200,
            'message': '获取成功',
            'data': serializer.data
        })
    
    def list(self, request, *args, **kwargs):
        """获取试卷列表"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'code': 200,
            'message': '获取成功',
            'data': serializer.data
        })

    def get_paginated_response(self, data):
        """自定义分页响应格式"""
        return Response({
            'code': 200,
            'message': '获取成功',
            'data': {
                'results': data,
                'count': self.paginator.page.paginator.count,
                'next': self.paginator.get_next_link(),
                'previous': self.paginator.get_previous_link(),
            }
        })
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['post'])
    def generate_paper(self, request):
        """
        自动组卷功能
        根据规则从题库中智能选择题目生成试卷
        """
        title = request.data.get('title')
        duration = request.data.get('duration')
        course = request.data.get('course')
        status = request.data.get('status', 0)  # 获取前端传递的状态，默认为草稿
        start_time = request.data.get('start_time')  # 获取开始时间
        end_time = request.data.get('end_time')  # 获取结束时间
        rules = request.data.get('rules', [])
        
        if not all([title, duration, course]):
            return Response({'code': 400, 'message': '请提供完整的试卷标题、时长和组卷规则'}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(rules, list) or not rules:
            return Response({'code': 400, 'message': '组卷规则格式错误，应为非空列表'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # 创建试卷
            paper = Paper.objects.create(
                title=title,
                duration=duration,
                course_id=course,
                created_by=request.user,
                status=status,  # 使用前端传递的状态
                start_time=start_time,  # 添加开始时间
                end_time=end_time  # 添加结束时间
            )

            total_score = 0
            paper_questions_to_create = []
            all_selected_question_ids = set()

            for i, rule in enumerate(rules):
                q_type = rule.get('type')
                count = rule.get('count')
                score_per_question = rule.get('score_per_question')

                if not all([q_type, count, score_per_question]):
                    return Response({'code': 400, 'message': f'第 {i+1} 条规则缺少必要参数'}, status=status.HTTP_400_BAD_REQUEST)

                # 按题型和课程筛选题目
                queryset = Question.objects.filter(
                    type=q_type,
                    course_id=course  # 添加课程过滤
                ).exclude(id__in=all_selected_question_ids)

                question_pool = list(queryset)
                if len(question_pool) < count:
                    type_name = dict(Question.TYPE_CHOICES).get(q_type, '未知题型')
                    return Response({'code': 400, 'message': f'{type_name}符合条件的题目不足 {count} 道'}, status=status.HTTP_400_BAD_REQUEST)

                # 智能选择算法：考虑题目多样性和随机性
                selected_questions = self._intelligent_question_selection(question_pool, count)
                all_selected_question_ids.update([q.id for q in selected_questions])

                for order, question in enumerate(selected_questions, start=len(paper_questions_to_create) + 1):
                    paper_questions_to_create.append(
                        PaperQuestion(
                            paper=paper,
                            question=question,
                            score=score_per_question,
                            order=order
                        )
                    )
                    total_score += score_per_question

            # 批量创建试卷题目关联
            PaperQuestion.objects.bulk_create(paper_questions_to_create)

            # 更新试卷总分
            paper.total_score = total_score
            paper.save()

        return Response({
            'code': 200,
            'message': '智能组卷成功',
            'data': {}
        })

    def _intelligent_question_selection(self, question_pool, count):
        """
        智能题目选择算法
        简化为随机选择，确保题目多样性
        """
        if not question_pool:
            return []
        
        # 如果题目数量刚好等于需要的数量，直接返回
        if len(question_pool) <= count:
            return question_pool
        
        # 随机选择指定数量的题目
        return random.sample(question_pool, count)

    @action(detail=False, methods=['get'])
    def student_papers(self, request):
        """学生获取自己的试卷列表"""
        student_papers = Paper.objects.filter(
            exam__student=request.user,
            exam__is_completed=True
        ).order_by('-exam__end_time')
        
        serializer = PaperStudentSerializer(student_papers, many=True)
        return Response({
            'code': 200,
            'message': '获取成功',
            'data': serializer.data
        })

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """发布试卷"""
        paper = self.get_object()
        if paper.status != 0:
            return Response({'code': 400, 'message': '只有草稿状态的试卷才能发布'}, status=status.HTTP_400_BAD_REQUEST)
        
        paper.status = 1
        paper.published_at = timezone.now()
        paper.save()
        
        return Response({'code': 200, 'message': '试卷发布成功'})

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """归档试卷"""
        paper = self.get_object()
        if paper.status == 2:
            return Response({'code': 400, 'message': '试卷已归档'}, status=status.HTTP_400_BAD_REQUEST)
        
        paper.status = 2
        paper.archived_at = timezone.now()
        paper.save()
        
        return Response({'code': 200, 'message': '试卷归档成功'})
