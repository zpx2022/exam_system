"""
用户认证路由
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# 管理员路由
admin_router = DefaultRouter()
admin_router.register(r'users', views.AdminUserViewSet, basename='admin-user')

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('public-key/', views.get_public_key, name='public-key'),
    path('user-info/', views.user_info, name='user-info'),
    path('update-info/', views.update_user_info, name='update-info'),
    path('change-password/send-code/', views.send_password_change_code, name='send-password-change-code'),
    path('change-password/', views.change_password, name='change-password'),
    path('forgot-password/send-code/', views.send_forgot_password_code, name='send-forgot-password-code'),
    path('forgot-password/reset/', views.reset_password, name='reset-password'),
    # 管理员路由
    path('admin/dashboard/stats/', views.admin_dashboard_stats, name='admin-dashboard-stats'),
    path('admin/', include(admin_router.urls)),
]




