from django.urls import path
from .views import GatewayReportView, GatewayStatusView

app_name = 'api_gateway'

urlpatterns = [
    path('reportes/', GatewayReportView.as_view(), name='reportes'),
    path('status/',   GatewayStatusView.as_view(), name='status'),
]
