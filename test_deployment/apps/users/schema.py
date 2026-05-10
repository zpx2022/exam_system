from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes


admin_user_list_extra_params = [
    OpenApiParameter(
        name='search',
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
        required=False,
        description='按用户名模糊搜索'
    ),
    OpenApiParameter(
        name='role',
        type=OpenApiTypes.INT,
        location=OpenApiParameter.QUERY,
        required=False,
        description='按角色过滤：0管理员/1教师/2学生'
    ),
    OpenApiParameter(
        name='is_active',
        type=OpenApiTypes.BOOL,
        location=OpenApiParameter.QUERY,
        required=False,
        description='按启用状态过滤：true/false'
    ),
]
