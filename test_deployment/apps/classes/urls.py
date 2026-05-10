"""
班级应用URL配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# 创建一个路由器并注册我们的视图集
router = DefaultRouter()
router.register(r'', views.ClassViewSet, basename='class')

# API URL由路由器自动确定
urlpatterns = [
    path('', include(router.urls)),
]
