"""
URL configuration for backend project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.users.urls')),
    path('api/questions/', include('apps.questions.urls')),
    path('api/papers/', include('apps.papers.urls')),
    path('api/exams/', include('apps.exams.urls')),
    path('api/courses/', include('apps.courses.urls')),
    path('api/classes/', include('apps.classes.urls')),

    # API Schema and Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# 媒体文件访问 - 明确添加路由
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # 额外的媒体文件路由，确保访问正常
    urlpatterns.append(path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}))
