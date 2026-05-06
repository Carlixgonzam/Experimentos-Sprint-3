import sys

from django.apps import AppConfig


class GeneradorReportesConfig(AppConfig):
    name = 'generador_reportes'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # No arrancar hilos durante makemigrations / migrate / shell, etc.
        management_commands = {'migrate', 'makemigrations', 'shell', 'test', 'collectstatic'}
        if management_commands.intersection(sys.argv):
            return
        from .heartbeat import HeartbeatSender
        HeartbeatSender.start()
