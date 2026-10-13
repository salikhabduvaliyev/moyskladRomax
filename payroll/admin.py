from django.contrib import admin
from .models import MoySkladConfig, KPIRules, ProductionCategory, Employee, PayrollPeriod, PayrollItem

@admin.register(MoySkladConfig)
class MoySkladConfigAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'base_url', 'is_active', 'last_synced_at')

@admin.register(KPIRules)
class KPIRulesAdmin(admin.ModelAdmin):
    list_display = ('sot_rate', 'sot_min', 'op_base', 'men_r2', 'ish_min', 'updated_at')

@admin.register(ProductionCategory)
class ProductionCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'prev_month_volume', 'growth_percent', 'plan', 'fact', 'tarif', 'order_num')
    list_editable = ('growth_percent', 'plan', 'fact', 'tarif', 'order_num')

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'position', 'group', 'oklad', 'production_category', 'is_active')
    list_filter = ('group', 'is_active', 'production_category')
    search_fields = ('name', 'position')
    list_editable = ('group', 'oklad', 'is_active')

class PayrollItemInline(admin.TabularInline):
    model = PayrollItem
    extra = 0
    fields = ('employee', 'group', 'oklad', 'plan', 'fact', 'percent', 'kpi_bonus', 'advance', 'total_salary', 'rest_to_pay')
    readonly_fields = ('percent', 'kpi_bonus', 'total_salary', 'rest_to_pay')

@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ('month', 'date_from', 'date_to', 'status', 'total_salary', 'total_rest', 'moysklad_expense_id')
    list_filter = ('status',)
    inlines = [PayrollItemInline]
