from django.urls import path
from .views import (
    SelfHealthView,
    HeartbeatView,
    SystemHealthView,
    ServiceHealthView,
    StaleServicesView,
)

app_name = 'monitor_servicios'

urlpatterns = [
    # Self health-check — Kong/otros te pinguean aquí
    path('health/', SelfHealthView.as_view(), name='self-health'),

    # Recibir heartbeats de los servicios monitoreados
    path('monitor/heartbeat/', HeartbeatView.as_view(), name='heartbeat'),

    # Estado de todos los servicios
    path('monitor/status/', SystemHealthView.as_view(), name='system-health'),

    # Estado de un servicio específico
    path('monitor/status/<str:service_name>/', ServiceHealthView.as_view(), name='service-health'),

    # Servicios caídos/tardíos
    path('monitor/stale/', StaleServicesView.as_view(), name='stale-services'),
]