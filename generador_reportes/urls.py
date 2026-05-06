from django.urls import path
from .views import ReportHealthView, GenerateReportView

app_name = 'generador_reportes'

urlpatterns = [
    path('health/', ReportHealthView.as_view(), name='health'),
    path('generar/', GenerateReportView.as_view(), name='generate'),
]
