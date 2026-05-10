"""
考试业务路由
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ExamRecordViewSet, MistakeBookViewSet, exam_statistics

router = DefaultRouter()
router.register(r'records', ExamRecordViewSet, basename='exam-record')
router.register(r'mistakes', MistakeBookViewSet, basename='mistake')

urlpatterns = [
    path('statistics/', exam_statistics, name='exam-statistics'),
    path('', include(router.urls)),  
]




