from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('fleet.urls')),
    path('accounts/', include('allauth.urls')),   # Google OAuth + allauth endpoints
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
