from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Sustainable Solutions Tanzania — administration"
admin.site.site_title = "SST admin"
admin.site.index_title = "Website, TakwimuBridge catalogue and TakwimuBridge QDA"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('datasets/', include('datasets.urls')),
    path('qda/', include('qda.urls')),
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
