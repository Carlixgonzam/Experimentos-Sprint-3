from django.contrib import admin
from .models import Business, ConsumptionSummary, CloudGovernance


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('id_business', 'name', 'nit')
    search_fields = ('name', 'nit')


@admin.register(ConsumptionSummary)
class ConsumptionSummaryAdmin(admin.ModelAdmin):
    list_display = ('id_business', 'month_year', 'total_usd_spent', 'payment_status')
    list_filter = ('payment_status', 'month_year')
    search_fields = ('id_business__name',)


@admin.register(CloudGovernance)
class CloudGovernanceAdmin(admin.ModelAdmin):
    list_display = ('id_business', 'responsible_area')
    search_fields = ('id_business__name', 'responsible_area')
