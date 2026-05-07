from django.urls import path
from .views import (
    GatewayReportView,
    GatewayStatusView,
    ExperimentKillView,
    ExperimentReviveView,
    ExperimentMeasureView,
)

app_name = 'api_gateway'

urlpatterns = [
    # Producción
    path('reportes/', GatewayReportView.as_view(), name='reportes'),
    path('status/', GatewayStatusView.as_view(), name='status'),

    # Experimento ASR de disponibilidad
    path('experimento/matar/<str:instance_name>/', ExperimentKillView.as_view(), name='kill'),
    path('experimento/revivir/<str:instance_name>/', ExperimentReviveView.as_view(), name='revive'),
    path('experimento/medir/', ExperimentMeasureView.as_view(), name='measure'),
]
