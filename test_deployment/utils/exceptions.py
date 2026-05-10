"""
自定义异常类
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    自定义异常处理
    """
    # 处理BusinessException
    if isinstance(exc, BusinessException):
        return Response({
            'code': exc.code,
            'message': exc.message,
            'data': None
        }, status=exc.code)
    
    # 处理DRF标准异常
    response = exception_handler(exc, context)
    
    if response is not None:
        custom_response_data = {
            'code': response.status_code,
            'message': str(exc),
            'data': None
        }
        
        # 处理验证错误
        if hasattr(exc, 'detail'):
            if isinstance(exc.detail, dict):
                errors = []
                for key, value in exc.detail.items():
                    if isinstance(value, list):
                        errors.append(f"{key}: {', '.join(str(v) for v in value)}")
                    else:
                        errors.append(f"{key}: {str(value)}")
                custom_response_data['message'] = '; '.join(errors)
            elif isinstance(exc.detail, list):
                custom_response_data['message'] = '; '.join(str(v) for v in exc.detail)
            else:
                custom_response_data['message'] = str(exc.detail)
        
        response.data = custom_response_data
    else:
        # 处理未捕获的异常
        logger.error(f"未处理的异常: {type(exc).__name__}: {str(exc)}", exc_info=True)
        return Response({
            'code': 500,
            'message': f'服务器内部错误: {str(exc)}',
            'data': None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return response


class BusinessException(Exception):
    """业务异常"""
    def __init__(self, message, code=400):
        self.message = message
        self.code = code
        super().__init__(self.message)




