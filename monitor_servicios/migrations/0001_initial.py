import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ServiceRegistration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('expected_interval_seconds', models.FloatField(default=30.0)),
                ('is_active', models.BooleanField(default=True)),
                ('registered_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Heartbeat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('received_at', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(
                    choices=[('ok', 'OK'), ('degraded', 'Degraded'), ('error', 'Error')],
                    default='ok', max_length=20)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('service', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='heartbeats',
                    to='monitor_servicios.serviceregistration')),
            ],
            options={
                'ordering': ['-received_at'],
                'get_latest_by': 'received_at',
            },
        ),
    ]
