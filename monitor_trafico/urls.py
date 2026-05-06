from django.urls import path
from .views import TrafficStatsView, BlockedIPListView, UnblockIPView

app_name = 'monitor_trafico'

urlpatterns = [
    path('stats/', TrafficStatsView.as_view(), name='stats'),
    path('blocked/', BlockedIPListView.as_view(), name='blocked-list'),
    path('unblock/<str:ip_address>/', UnblockIPView.as_view(), name='unblock'),
]
