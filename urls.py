"""
URL Configuration raíz del monolito.
Cada componente tiene su propio namespace y prefijo de ruta.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Monitor de Tráfico
    path('api/monitor-trafico/', include('monitor_trafico.urls', namespace='monitor_trafico')),

    # Monitor de Servicios
    path('api/monitor-servicios/', include('monitor_servicios.urls', namespace='monitor_servicios')),

    # Generador de Reportes
    path('api/generador-reportes/', include('generador_reportes.urls', namespace='generador_reportes')),

    # Recolector de Inventarios
    path('api/recolector/', include('recolector_inventarios.urls', namespace='recolector_inventarios')),
]
