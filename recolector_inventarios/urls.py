from django.urls import path
from . import views

app_name = 'recolector_inventarios'

urlpatterns = [
    # PostgreSQL
    path('businesses/<str:business_id>/USDConsumption',
         views.USDConsumptionView.as_view(),  name='usd-consumption'),

    path('businesses/<str:business_id>/CloudGovernance',
         views.CloudGovernanceView.as_view(), name='cloud-governance'),

    # MongoDB
    path('businesses/<str:business_id>/S3Usage',
         views.S3UsageView.as_view(),         name='s3-usage'),

    path('businesses/<str:business_id>/EC2Usage',
         views.EC2UsageView.as_view(),        name='ec2-usage'),
]