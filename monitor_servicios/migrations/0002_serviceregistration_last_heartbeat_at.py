# monitor_servicios/migrations/0002_serviceregistration_last_heartbeat_at.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitor_servicios', '0001_initial'),
    ]

    operations = [
        # Agrega last_heartbeat_at a ServiceRegistration.
        # nullable=True para que no rompa registros existentes.
        migrations.AddField(
            model_name='serviceregistration',
            name='last_heartbeat_at',
            field=models.DateTimeField(blank=True, null=True),
        ),

        # Agrega los nuevos choices 'recovered' y 'timeout' al campo status
        # de Heartbeat (CharField, no requiere cambio de columna en Postgres/SQLite).
        migrations.AlterField(
            model_name='heartbeat',
            name='status',
            field=models.CharField(
                choices=[
                    ('ok',        'OK'),
                    ('degraded',  'Degraded'),
                    ('error',     'Error'),
                    ('recovered', 'Recovered'),
                    ('timeout',   'Timeout'),
                ],
                default='ok',
                max_length=20,
            ),
        ),
    ]
