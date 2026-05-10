"""
分页器配置
"""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    # 移除 max_page_size 限制，允许前端自定义页面大小
    
    def get_paginated_response(self, data):
        """
        重写分页响应格式，使其符合前端期望的格式
        """
        return Response({
            'code': 200,
            'message': '获取成功',
            'data': {
                'count': self.page.paginator.count,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'results': data
            }
        })




