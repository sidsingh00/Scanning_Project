from django.url import path, include
from rest_framework import DefaultRouter
from . import views

router = DefaultRouter()

urlpatterns = [
    path('',views.ScannedItemListCreateView.as_view(),name='scan-list'),
    path('<int:pk>/',views.ScannedItemDetailView.as_view(),name='scan-detail'),
    path('bulk/',views.bulk_scan_create,name='bulk-scan'),
    path('stats/',views.scan_stats,name='scan-stats'),
    path('stats',views.recent_scans,name='recent-scans'),
]