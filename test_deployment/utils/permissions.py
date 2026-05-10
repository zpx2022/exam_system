"""
权限类
"""
from rest_framework import permissions
import logging

logger = logging.getLogger(__name__)


class IsTeacher(permissions.BasePermission):
    """教师权限"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"权限验证失败: 用户未认证, 路径: {request.path}")
            return False
        if request.user.role != 1:
            logger.warning(f"权限验证失败: 用户='{request.user.username}', 角色值='{request.user.role}', 角色类型='{type(request.user.role)}', 期望值='1', 期望类型='<class 'int'>'")
            return False
        return True


class IsStudent(permissions.BasePermission):
    """学生权限"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"权限验证失败: 用户未认证, 路径: {request.path}")
            return False
        if request.user.role != 2:
            logger.warning(f"权限验证失败: 用户='{request.user.username}', 角色值='{request.user.role}', 期望值='2'")
            return False
        return True


class IsAdmin(permissions.BasePermission):
    """管理员权限"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"权限验证失败: 用户未认证, 路径: {request.path}")
            return False
        if request.user.role != 0:
            logger.warning(f"权限验证失败: 用户='{request.user.username}', 角色值='{request.user.role}', 期望值='0'")
            return False
        return True


class IsAdminOrTeacher(permissions.BasePermission):
    """管理员或教师权限"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"权限验证失败: 用户未认证, 路径: {request.path}")
            return False
        return request.user.role in [0, 1]  # 管理员或教师





