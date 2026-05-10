"""
考试业务视图
"""
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.db import transaction

from utils.permissions import IsStudent, IsTeacher
from utils.redis_client import redis_client
from utils.exceptions import BusinessException
from django.db.models import Q
from utils.pagination import StandardResultsSetPagination
from .models import ExamRecord, StudentAnswer, MistakeBook
from .serializers import ExamRecordSerializer, ExamRecordDetailSerializer, ExamRecordListSerializer, MistakeBookSerializer, ExamRecordDetailSerializer, ExamResultSerializer
from apps.papers.models import Paper
import json



class ExamRecordViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """考试记录视图集"""
    queryset = ExamRecord.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_serializer_class(self):
        # schema 生成阶段（drf-spectacular）没有真实 request.user，上来就访问 role 会报错
        if getattr(self, 'swagger_fake_view', False):
            return ExamRecordSerializer

        if self.action == 'list':
            return ExamRecordListSerializer
        elif self.action == 'retrieve':
            # 详情：区分教师 / 学生复盘
            user = getattr(self.request, 'user', None)
            role = getattr(user, 'role', None)

            if role == 1:
                # 教师看详情（含答案）
                return ExamRecordDetailSerializer
            elif role == 2:
                # 学生：若成绩发布显示复盘，否则基础信息
                record = self.get_object() if hasattr(self, 'get_object') else None
                if record and record.status == 3:
                    return ExamResultSerializer
            # 默认
            return ExamRecordSerializer
        return ExamRecordSerializer
    
    def get_queryset(self):
        """过滤查询集"""
        queryset = ExamRecord.objects.all()
        
        # 学生只能看自己的
        if self.request.user.role == 2:
            queryset = queryset.filter(student=self.request.user)
        # 教师只能看自己创建的试卷的考试记录
        elif self.request.user.role == 1:
            queryset = queryset.filter(paper__created_by=self.request.user)
        
        # 自动更新状态：检查考试时间窗口结束后且阅卷完成的记录
        from django.utils import timezone
        now = timezone.now()
        
        # 批量更新状态：教师已阅卷且考试时间窗口结束的记录
        records_to_update = []
        for record in queryset:
            if (record.status == 2 and  # 教师已阅卷
                record.is_grading_completed() and  # 阅卷完成
                record.paper.end_time and 
                now >= record.paper.end_time):  # 时间窗口结束
                records_to_update.append(record)
        
        # 批量更新状态为已完成
        if records_to_update:
            ExamRecord.objects.filter(
                id__in=[r.id for r in records_to_update]
            ).update(status=3)
        
        # 按状态过滤
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # 按试卷过滤
        paper_id_filter = self.request.query_params.get('paper_id')
        if paper_id_filter:
            queryset = queryset.filter(paper_id=paper_id_filter)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """考试记录列表"""
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
    
    def retrieve(self, request, *args, **kwargs):
        """获取考试记录详情"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'code': 200,
            'message': '获取成功',
            'data': serializer.data
        })
    
    @action(detail=False, methods=['post'])
    def start_exam(self, request):
        """开始考试，支持预览模式"""
        paper_id = request.data.get('paper_id')
        is_preview = request.data.get('preview', False)

        if not paper_id:
            raise BusinessException("请选择试卷", code=400)

        now = timezone.now()
        try:
            paper = Paper.objects.filter(
                Q(start_time__isnull=True) | Q(start_time__lte=now),
                Q(end_time__isnull=True) | Q(end_time__gte=now),
                id=paper_id,
                status=1
            ).get()
        except Paper.DoesNotExist:
            raise BusinessException("试卷不存在、未发布或不在考试有效期内", code=404)

        # 计算有效考试时长
        effective_duration_seconds = paper.duration * 60
        if paper.end_time:
            time_left_seconds = (paper.end_time - now).total_seconds()
            effective_duration_seconds = min(effective_duration_seconds, int(time_left_seconds))

        effective_duration_seconds = max(0, effective_duration_seconds)

        # 如果是预览模式，只返回计算出的时间
        if is_preview:
            return Response({
                'code': 200,
                'message': '预览成功',
                'data': {
                    'remaining_seconds': effective_duration_seconds,
                    'full_duration_seconds': paper.duration * 60
                }
            })

        # --- 正式开始考试逻辑 ---
        # 检查是否已有该试卷的考试记录
        existing_record = ExamRecord.objects.filter(student=request.user, paper=paper).first()
        existing = None

        if existing_record:
            # 如果记录不是"进行中"，说明已提交，禁止再次进入
            if existing_record.status != 0:
                raise BusinessException("您已提交过该试卷，无法再次进入", code=400)
            
            # 记录为"进行中"，允许继续考试
            existing = existing_record

        if existing:
            # 如果是继续考试，我们应该返回Redis中真实的剩余时间
            remaining_from_redis = redis_client.get_exam_remaining_time(existing.id)

            # 如果Redis中没有计时器（例如服务器重启），则重新设置
            if remaining_from_redis is None:
                time_passed = (now - existing.start_time).total_seconds()
                # The original duration for this record was `effective_duration_seconds` at the time it was created.
                # We need to recalculate that original effective duration.
                original_start_effective_duration = paper.duration * 60
                if paper.end_time:
                    original_start_effective_duration = min(original_start_effective_duration, (paper.end_time - existing.start_time).total_seconds())

                new_remaining = max(0, original_start_effective_duration - time_passed)
                redis_client.set_exam_timer(existing.id, new_remaining)
                remaining_from_redis = int(new_remaining)
            
            # The final remaining time is the minimum of what's left in redis and what's left until the paper's end time.
            final_remaining = remaining_from_redis
            if paper.end_time:
                time_left_until_end = max(0, (paper.end_time - now).total_seconds())
                final_remaining = min(final_remaining, int(time_left_until_end))

            existing_data = ExamRecordSerializer(existing).data
            existing_data['remaining_seconds'] = final_remaining
            return Response({
                'code': 200,
                'message': '继续考试',
                'data': existing_data
            })

        # 创建新记录
        record = ExamRecord.objects.create(student=request.user, paper=paper, status=0)
        redis_client.set_exam_timer(record.id, effective_duration_seconds)
        
        return Response({
            'code': 200,
            'message': '考试开始',
            'data': {
                'remaining_seconds': effective_duration_seconds
            }
        })
    
    @action(detail=True, methods=['get'])
    def sync_time(self, request, pk=None):
        """同步考试时间"""
        record = self.get_object()
        
        # 检查权限
        if request.user.role == 2 and record.student != request.user:
            raise BusinessException("无权访问", code=403)
        
        # 从Redis获取剩余时间
        remaining_from_redis = redis_client.get_exam_remaining_time(record.id)
        
        # 检查试卷的固定结束时间
        now = timezone.now()
        paper = record.paper
        remaining_until_end_time = None
        if paper.end_time:
            if now > paper.end_time:
                remaining_until_end_time = 0
            else:
                remaining_until_end_time = int((paper.end_time - now).total_seconds())
        
        # 取两者中的较小值作为最终剩余时间
        final_remaining = remaining_from_redis
        if remaining_until_end_time is not None:
            if final_remaining is None:
                final_remaining = remaining_until_end_time
            else:
                final_remaining = min(final_remaining, remaining_until_end_time)
        
        # 如果Redis中没有计时器，但考试仍在进行中，需要处理
        if final_remaining is None and record.status == 0:
            # 可能是Redis数据丢失，根据开始时间重新计算
            time_passed = (now - record.start_time).total_seconds()
            effective_duration = paper.duration * 60
            if paper.end_time and (paper.end_time - record.start_time).total_seconds() < effective_duration:
                effective_duration = (paper.end_time - record.start_time).total_seconds()
            final_remaining = max(0, int(effective_duration - time_passed))
            # 将重新计算的时间写回Redis
            redis_client.set_exam_timer(record.id, final_remaining)

        final_remaining = final_remaining or 0

        if final_remaining <= 0 and record.status == 0:
            # 时间已到，自动提交
            record.status = 1
            record.end_time = now
            record.save()
            # 确保Redis计时器被删除
            redis_client.delete_exam_timer(record.id)
            # 自动评分
            self._auto_grade(record)
        
        return Response({
            'code': 200,
            'message': '获取成功',
            'data': {
                'remaining_seconds': final_remaining,
                'status': record.status
            }
        })
    
    @action(detail=True, methods=['get'])
    def get_cached_answers(self, request, pk=None):
        """获取Redis缓存的答案（用于恢复）"""
        record = self.get_object()
        
        # 权限检查
        if request.user.role == 2 and record.student != request.user:
            raise BusinessException("无权访问", code=403)
        if record.status != 0:
            raise BusinessException("考试已结束", code=400)
        
        # 从Redis获取答案
        cached_answers = redis_client.get_student_answers(record.id)
        
        return Response({
            'code': 200,
            'data': cached_answers or {}
        })

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def submit_answer(self, request, pk=None):
        """提交/保存答案（支持批量）- 使用Redis缓存优化"""
        record = self.get_object()

        # 权限与状态检查
        if request.user.role == 2 and record.student != request.user:
            raise BusinessException("无权访问", code=403)
        if record.status != 0:
            raise BusinessException("考试已结束，无法保存答案", code=400)

        # 时间检查
        remaining = redis_client.get_exam_remaining_time(record.id)
        if remaining is not None and remaining <= 0:
            raise BusinessException("考试时间已到，无法保存答案", code=400)

        answers = request.data.get('answers', {})
        if not isinstance(answers, dict):
            raise BusinessException("答案格式错误，应为 {'question_id': answer, ...} 格式", code=400)

        from apps.questions.models import Question

        # 验证题目存在性
        question_ids = [int(qid) for qid in answers.keys()]
        questions = Question.objects.in_bulk(question_ids)
        
        # 验证所有题目都存在
        invalid_questions = [qid for qid in question_ids if qid not in questions]
        if invalid_questions:
            raise BusinessException(f"题目ID {invalid_questions} 不存在", code=400)

        # 第一道防线：保存到Redis缓存（高性能）
        current_answers = redis_client.get_student_answers(record.id) or {}
        
        for qid, answer_content in answers.items():
            current_answers[str(qid)] = answer_content
        
        redis_client.cache_student_answers(record.id, current_answers, ttl=7200)

        return Response({
            'code': 200,
            'message': '答案已缓存',
            'data': None
        })

    @action(detail=False, methods=['post'])
    def start_exam(self, request):
        """开始考试，支持预览模式"""
        paper_id = request.data.get('paper_id')
        is_preview = request.data.get('preview', False)

        if not paper_id:
            raise BusinessException("请选择试卷", code=400)

        now = timezone.now()
        try:
            paper = Paper.objects.filter(
                Q(start_time__isnull=True) | Q(start_time__lte=now),
                Q(end_time__isnull=True) | Q(end_time__gte=now),
                id=paper_id,
                status=1
            ).get()
        except Paper.DoesNotExist:
            raise BusinessException("试卷不存在、未发布或不在考试有效期内", code=404)

        # 计算有效考试时长
        effective_duration_seconds = paper.duration * 60
        if paper.end_time:
            time_left_seconds = (paper.end_time - now).total_seconds()
            effective_duration_seconds = min(effective_duration_seconds, int(time_left_seconds))

        effective_duration_seconds = max(0, effective_duration_seconds)

        # 如果是预览模式，只返回计算出的时间
        if is_preview:
            return Response({
                'code': 200,
                'message': '预览成功',
                'data': {
                    'remaining_seconds': effective_duration_seconds,
                    'full_duration_seconds': paper.duration * 60
                }
            })

        # --- 正式开始考试逻辑 ---
        # 检查是否已有该试卷的考试记录
        existing_record = ExamRecord.objects.filter(student=request.user, paper=paper).first()
        existing = None

        if existing_record:
            # 如果记录不是"进行中"，说明已提交，禁止再次进入
            if existing_record.status != 0:
                raise BusinessException("您已提交过该试卷，无法再次进入", code=400)
            
            # 记录为"进行中"，允许继续考试
            existing = existing_record

        if existing:
            # 如果是继续考试，我们应该返回Redis中真实的剩余时间
            remaining_from_redis = redis_client.get_exam_remaining_time(existing.id)

            # 如果Redis中没有计时器（例如服务器重启），则重新设置
            if remaining_from_redis is None:
                time_passed = (now - existing.start_time).total_seconds()
                # The original duration for this record was `effective_duration_seconds` at the time it was created.
                # We need to recalculate that original effective duration.
                original_start_effective_duration = paper.duration * 60
                if paper.end_time:
                    original_start_effective_duration = min(original_start_effective_duration, (paper.end_time - existing.start_time).total_seconds())

                new_remaining = max(0, original_start_effective_duration - time_passed)
                redis_client.set_exam_timer(existing.id, new_remaining)
                remaining_from_redis = int(new_remaining)
            
            # The final remaining time is the minimum of what's left in redis and what's left until the paper's end time.
            final_remaining = remaining_from_redis
            if paper.end_time:
                time_left_until_end = max(0, (paper.end_time - now).total_seconds())
                final_remaining = min(final_remaining, int(time_left_until_end))

            existing_data = ExamRecordSerializer(existing).data
            existing_data['remaining_seconds'] = final_remaining
            return Response({
                'code': 200,
                'message': '继续考试',
                'data': existing_data
            })

        # 创建新记录
        record = ExamRecord.objects.create(student=request.user, paper=paper, status=0)
        redis_client.set_exam_timer(record.id, effective_duration_seconds)
        
        record_data = ExamRecordSerializer(record).data
        record_data['remaining_seconds'] = effective_duration_seconds
        
        return Response({
            'code': 200,
            'message': '考试开始',
            'data': record_data
        })

    # submit_exam method will be recreated here
    
    @action(detail=True, methods=['post'])
    def submit_exam(self, request, pk=None):
        """交卷"""
        record = self.get_object()
        is_time_up = False

        # 检查状态
        if record.status != 0:
            raise BusinessException("考试已结束或已交卷", code=400)

        # 检查时间
        remaining = redis_client.get_exam_remaining_time(record.id)
        if remaining is None or remaining <= 0:
            is_time_up = True

        # 从Redis获取缓存的答案
        cached_answers = redis_client.get_student_answers(record.id) or {}
        
        # 合并最后答案
        final_answers = request.data.get('answers', {})
        if final_answers and isinstance(final_answers, dict):
            cached_answers.update(final_answers)
            # 更新Redis缓存
            redis_client.cache_student_answers(record.id, cached_answers, ttl=7200)

        # 第二道防线：将Redis中的答案同步到MySQL数据库
        if cached_answers:
            from .models import StudentAnswer
            from apps.questions.models import Question

            question_ids = [int(qid) for qid in cached_answers.keys()]
            questions = Question.objects.in_bulk(question_ids)

            for qid, answer_content in cached_answers.items():
                question_id = int(qid)
                if question_id not in questions:
                    continue
                
                student_answer, created = StudentAnswer.objects.get_or_create(
                    exam_record=record,
                    question_id=question_id
                )
                student_answer.set_answer(answer_content)
                student_answer.save()

        # 更新状态为"批改中"，等待自动评分和教师阅卷
        record.status = 1  # 1 表示 '批改中'
        record.end_time = timezone.now()
        record.save()

        # 删除Redis缓存（考试已结束）
        redis_client.delete_exam_timer(record.id)
        redis_client.delete_student_answers(record.id)

        # 自动评分
        # 自动批改（客观题）
        self._auto_grade(record)

        return Response({
            'code': 200,
            'message': '交卷成功',
            'data': {
                'record_id': record.id,
                'end_time': record.end_time.isoformat()
            }
        })
    
    def _auto_grade(self, record):
        """自动批改客观题，并更新每题得分"""
        from apps.papers.models import PaperQuestion
        from .models import StudentAnswer

        # 获取该次考试的所有学生答案，并预加载问题和试卷问题信息
        student_answers = StudentAnswer.objects.filter(exam_record=record).select_related('question')
        paper_questions_map = {pq.question_id: pq for pq in PaperQuestion.objects.filter(paper=record.paper)}

        total_score = 0
        has_subjective_question = False

        for sa in student_answers:
            question = sa.question
            pq = paper_questions_map.get(question.id)

            if not pq:
                continue # 理论上不应该发生

            # 如果是主观题，标记并跳过
            if question.type == 4: # 简答题
                has_subjective_question = True
                continue

            # --- 客观题自动评分逻辑 ---
            user_answer = sa.get_answer()
            correct_answer = question.get_answer()
            is_correct = False

            try:
                if question.type in [1, 3]:  # 单选、判断
                    # 修复：确保都是字符串比较，并去除前后空格
                    user_str = str(user_answer).strip() if user_answer else ''
                    correct_str = str(correct_answer).strip() if correct_answer else ''
                    
                    # 特殊处理判断题：将选项键转换为实际内容
                    if question.type == 3:
                        # 判断题选项映射：A->正确, B->错误
                        judgment_map = {'A': '正确', 'B': '错误'}
                        # 如果正确答案是选项键，转换为实际内容
                        correct_str = judgment_map.get(correct_str.upper(), correct_str)
                    
                    is_correct = user_str == correct_str
                    
                elif question.type == 2:  # 多选
                    # 前后端约定：多选答案为数组，例如 ['A','C']
                    if isinstance(user_answer, list):
                        user_ans_list = sorted([str(x).strip() for x in user_answer if str(x).strip()])
                    else:
                        user_ans_list = []

                    if isinstance(correct_answer, list):
                        correct_ans_list = sorted([str(x).strip() for x in correct_answer if str(x).strip()])
                    else:
                        correct_ans_list = []

                    is_correct = user_ans_list == correct_ans_list
            except Exception:
                is_correct = False # 答案格式异常，判错

            if is_correct:
                sa.set_score(pq.score)  # ✅ 使用加密方法
                total_score += pq.score
            else:
                sa.set_score(0)         # ✅ 使用加密方法
                # 记录错题（仅引用 StudentAnswer，避免明文存储答案）
                MistakeBook.objects.update_or_create(
                    student=record.student,
                    question=question,
                    exam_record=record,
                    defaults={
                        'student_answer': sa,
                    }
                )
            sa.save()

        # 更新总分和状态
        record.set_score(total_score)  # ✅ 使用加密方法
        
        # 检查考试时间窗口是否结束
        from django.utils import timezone
        exam_window_ended = not record.paper.end_time or timezone.now() >= record.paper.end_time
        
        # 如果有主观题或考试时间窗口未结束，状态变为"批改中"，只有都满足才"教师已阅卷"
        if has_subjective_question or not exam_window_ended:
            record.status = 1  # 批改中
        else:
            record.status = 2  # 教师已阅卷（无主观题且时间窗口结束）
        record.save()

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsTeacher])
    @transaction.atomic
    def reset_exam(self, request, pk=None):
        """重置考试（删除记录，允许学生重考）"""
        record = self.get_object()

        # 安全校验：只允许重置状态为0、1、2的考试（进行中、批改中、教师已阅卷）
        if record.status >= 3:
            raise BusinessException("考试已完成，无法重置", code=400)

        # 删除Redis倒计时
        redis_client.delete_exam_timer(record.id)

        # 删除考试记录（相关的StudentAnswer和MistakeBook将级联删除）
        record.delete()

        return Response({
            'code': 200,
            'message': '重置成功，学生可以重新参加考试',
            'data': None
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsTeacher])
    @transaction.atomic
    def grade(self, request, pk=None):
        """教师评分（主观题），并汇总总分"""
        record = self.get_object()

        # 检查状态，只允许在"批改中"或"教师已阅卷"时操作
        # 时间控制：只有考试结束后才能阅卷（状态0表示进行中）
        if record.status == 0:
            raise BusinessException("考试进行中，暂不能阅卷", code=400)
        if record.status not in [1, 2]:
            raise BusinessException("当前状态无法评分", code=400)

        scores_data = request.data.get('scores', {})
        if not isinstance(scores_data, dict):
            raise BusinessException("评分数据格式错误", code=400)

        from .models import StudentAnswer
        from apps.papers.models import PaperQuestion
        from django.db.models import Sum
        from apps.questions.models import Question
        from .models import MistakeBook

        # 获取试卷题目配置，用于校验分数上限
        paper_questions_map = {pq.question_id: pq for pq in PaperQuestion.objects.filter(paper=record.paper)}

        # 批量更新主观题分数
        for qid, score in scores_data.items():
            try:
                question_id = int(qid)
                pq = paper_questions_map.get(question_id)
                if not pq or pq.question.type != 4: # 确保是试卷中的主观题
                    continue

                score_val = float(score)
                # 校验分数是否超限
                if score_val > pq.score:
                    score_val = pq.score
                if score_val < 0:
                    score_val = 0

                # 更新或获取学生答案记录
                sa, created = StudentAnswer.objects.get_or_create(
                    exam_record=record,
                    question_id=question_id,
                    defaults={'score': ''},  # 创建时使用空值
                )
                if created or sa.get_score() != score_val:
                    sa.set_score(score_val)  # ✅ 使用加密方法
                    sa.save()

                # 未满分的主观题加入错题本（仅引用 StudentAnswer）
                if score_val < float(pq.score):
                    q_obj = pq.question

                    MistakeBook.objects.update_or_create(
                        student=record.student,
                        question=q_obj,
                        exam_record=record,
                        defaults={
                            'student_answer': sa,
                        }
                    )
            except (ValueError, TypeError):
                continue # 忽略格式错误的分数

        # 计算总分：客观题分数 + 主观题分数
        # 先获取客观题分数（已自动评分）
        objective_score = 0
        for sa in StudentAnswer.objects.filter(exam_record=record, question__type__in=[1,2,3]):  # 单选、多选、判断
            score = sa.get_score()
            if score is not None:
                objective_score += score
        
        # 再获取主观题分数（教师刚评分的）
        subjective_score = 0
        for sa in StudentAnswer.objects.filter(exam_record=record, question__type=4):  # 简答题
            score = sa.get_score()
            if score is not None:
                subjective_score += score
        
        final_score = objective_score + subjective_score

        # 更新总分和状态
        record.set_score(final_score)  # ✅ 使用加密方法
        
        # 检查考试时间窗口是否结束
        from django.utils import timezone
        exam_window_ended = not record.paper.end_time or timezone.now() >= record.paper.end_time
        
        if exam_window_ended:
            # 考试时间窗口结束，教师评分后可以发布成绩
            record.status = 3  # 已完成（可查看成绩）
        else:
            # 考试时间窗口未结束，教师评分完成但等待时间窗口
            record.status = 2  # 教师已阅卷
        record.save()

        return Response({
            'code': 200,
            'message': '评分成功',
            'data': ExamRecordSerializer(record).data
        })


class MistakeBookViewSet(viewsets.ReadOnlyModelViewSet):
    """错题本视图集"""
    queryset = MistakeBook.objects.all()
    serializer_class = MistakeBookSerializer
    permission_classes = [IsAuthenticated, IsStudent]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """只返回当前学生的错题"""
        queryset = MistakeBook.objects.filter(
            student=self.request.user
        ).select_related('question', 'exam_record').order_by('-created_at')
        
        # 权限控制：只有考试已完成（状态3）的错题才能查看
        queryset = queryset.filter(exam_record__status=3)
        
        # 支持按题型过滤
        question_type = self.request.query_params.get('question_type')
        if question_type:
            try:
                question_type = int(question_type)
                queryset = queryset.filter(question__type=question_type)
            except (ValueError, TypeError):
                pass
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """错题本列表"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # 错题本API不使用分页，直接返回所有数据
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'code': 200,
            'message': '获取成功',
            'data': serializer.data
        })


@extend_schema(
    request=None,
    parameters=[
        __import__('drf_spectacular.utils').utils.OpenApiParameter(
            name='paper_id',
            type=__import__('drf_spectacular.types').types.OpenApiTypes.INT,
            location=__import__('drf_spectacular.utils').utils.OpenApiParameter.QUERY,
            required=False,
        ),
        __import__('drf_spectacular.utils').utils.OpenApiParameter(
            name='start_date',
            type=__import__('drf_spectacular.types').types.OpenApiTypes.STR,
            location=__import__('drf_spectacular.utils').utils.OpenApiParameter.QUERY,
            required=False,
        ),
        __import__('drf_spectacular.utils').utils.OpenApiParameter(
            name='end_date',
            type=__import__('drf_spectacular.types').types.OpenApiTypes.STR,
            location=__import__('drf_spectacular.utils').utils.OpenApiParameter.QUERY,
            required=False,
        ),
    ],
    responses={
        200: inline_serializer(
            name='ExamStatisticsResponse',
            fields={
                'code': __import__('rest_framework').serializers.IntegerField(),
                'message': __import__('rest_framework').serializers.CharField(),
                'data': inline_serializer(
                    name='ExamStatisticsData',
                    fields={
                        'total_count': __import__('rest_framework').serializers.IntegerField(),
                        'average_score': __import__('rest_framework').serializers.FloatField(),
                        'max_score': __import__('rest_framework').serializers.FloatField(),
                        'min_score': __import__('rest_framework').serializers.FloatField(),
                        'pass_count': __import__('rest_framework').serializers.IntegerField(),
                        'pass_rate': __import__('rest_framework').serializers.FloatField(),
                        'score_distribution': __import__('rest_framework').serializers.ListField(child=__import__('rest_framework').serializers.DictField(), required=False),
                        'paper_list': __import__('rest_framework').serializers.ListField(child=__import__('rest_framework').serializers.DictField(), required=False),
                    },
                ),
            },
        )
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacher])
def exam_statistics(request):
    """
    成绩统计分析（教师端）
    支持按试卷、时间范围等维度统计
    """
    from apps.papers.models import Paper
    from django.db.models import Avg, Count, Max, Min, Q
    from datetime import datetime, timedelta
    
    paper_id = request.query_params.get('paper_id')
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    # 构建查询条件
    # status 语义：0进行中/1批改中/2教师已阅卷/3已完成(可查看成绩)
    # 统计应以"已完成"的最终成绩为准
    queryset = ExamRecord.objects.filter(status__in=[3])
    
    if paper_id:
        queryset = queryset.filter(paper_id=paper_id)
    
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            start = timezone.make_aware(start, timezone.get_current_timezone())
            queryset = queryset.filter(start_time__gte=start)
        except:
            pass
    
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            end = timezone.make_aware(end, timezone.get_current_timezone())
            queryset = queryset.filter(start_time__lt=end)
        except:
            pass
    
    # 统计信息
    total_count = queryset.count()
    
    if total_count == 0:
        return Response({
            'code': 200,
            'message': '获取成功',
            'data': {
                'total_count': 0,
                'average_score': 0,
                'max_score': 0,
                'min_score': 0,
                'pass_count': 0,
                'pass_rate': 0,
                'score_distribution': [],
                'paper_list': []
            }
        })
    
    # 基础统计 - 需要解密分数后进行统计
    stats_values = {'total': 0, 'count': 0, 'max': 0, 'min': float('inf')}
    pass_count = 0
    pass_score = 60  # 及格分数
    
    for record in queryset:
        score = record.get_score()  # 使用解密方法
        if score is not None:
            stats_values['total'] += score
            stats_values['count'] += 1
            stats_values['max'] = max(stats_values['max'], score)
            stats_values['min'] = min(stats_values['min'], score)
            if score >= pass_score:
                pass_count += 1
    
    # 计算平均值和及格率
    avg_score = stats_values['total'] / stats_values['count'] if stats_values['count'] > 0 else 0
    pass_rate = round(pass_count / stats_values['count'] * 100, 2) if stats_values['count'] > 0 else 0
    
    stats = {
        'avg_score': avg_score,
        'max_score': stats_values['max'] if stats_values['max'] != float('inf') else 0,
        'min_score': stats_values['min'] if stats_values['min'] != float('inf') else 0
    }
    
    # 分数分布（0-59, 60-69, 70-79, 80-89, 90-100）- 使用解密后的分数
    score_ranges = [
        {'range': '0-59', 'min': 0, 'max': 59},
        {'range': '60-69', 'min': 60, 'max': 69},
        {'range': '70-79', 'min': 70, 'max': 79},
        {'range': '80-89', 'min': 80, 'max': 89},
        {'range': '90-100', 'min': 90, 'max': 100}
    ]
    
    score_distribution = []
    for range_info in score_ranges:
        count = 0
        for record in queryset:
            score = record.get_score()
            if score is not None and range_info['min'] <= score <= range_info['max']:
                count += 1
        score_distribution.append({
            'range': range_info['range'],
            'count': count
        })
    
    # 按试卷统计 - 使用解密后的分数
    from django.db.models import Count, Q
    from apps.users.models import User
    
    paper_records = {}
    
    # 首先获取每个试卷应该参加考试的总人数
    paper_total_students = {}
    for paper in set(record.paper for record in queryset):
        # 获取试卷指定的所有班级
        target_classes = paper.target_classes.all()
        
        # 如果没有直接关联班级，检查是否通过课程关联
        if target_classes.count() == 0 and paper.course:
            # 通过课程获取关联的班级
            target_classes = paper.course.classes.all()
        
        if target_classes.count() == 0:
            # 如果试卷没有指定任何班级，无法计算缺考人数
            total_students = 0
        else:
            total_students = User.objects.filter(
                role=2,  # 学生角色
                student_class__in=target_classes
            ).count()
        paper_total_students[paper.id] = total_students
    
    for record in queryset:
        paper_id = record.paper.id
        if paper_id not in paper_records:
            paper_records[paper_id] = {
                'paper_id': paper_id,
                'paper_title': record.paper.title,
                'scores': [],
                'count': 0
            }
        score = record.get_score()
        if score is not None:
            paper_records[paper_id]['scores'].append(score)
            paper_records[paper_id]['count'] += 1
    
    paper_list = []
    for paper_id, data in paper_records.items():
        scores = data['scores']
        total_students = paper_total_students.get(paper_id, 0)
        
        if total_students == 0:
            # 如果试卷没有指定班级，无法计算缺考人数
            absent_count = "N/A"
        else:
            absent_count = max(0, total_students - data['count'])  # 缺考人数 = 应参加 - 实际参加
        
        if scores:
            paper_list.append({
                'paper_id': data['paper_id'],
                'paper_title': data['paper_title'],
                'exam_count': data['count'],
                'absent_count': absent_count,
                'average_score': round(sum(scores) / len(scores), 2),
                'max_score': round(max(scores), 2),
                'min_score': round(min(scores), 2)
            })
        else:
            paper_list.append({
                'paper_id': data['paper_id'],
                'paper_title': data['paper_title'],
                'exam_count': data['count'],
                'absent_count': absent_count,
                'average_score': 0,
                'max_score': 0,
                'min_score': 0
            })
    
    return Response({
        'code': 200,
        'message': '获取成功',
        'data': {
            'total_count': total_count,
            'average_score': round(stats['avg_score'], 2),
            'max_score': round(stats['max_score'], 2),
            'min_score': round(stats['min_score'], 2),
            'pass_count': pass_count,
            'pass_rate': pass_rate,
            'score_distribution': score_distribution,
            'paper_list': paper_list
        }
    })



