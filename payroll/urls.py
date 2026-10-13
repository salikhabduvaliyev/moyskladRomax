from django.urls import path
from . import views

app_name = 'payroll'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/period-data/', views.get_period_data, name='period_data'),
    path('api/save-rules/', views.save_rules_and_categories, name='save_rules'),
    path('api/update-items/', views.update_payroll_items, name='update_items'),
    path('api/calculate/', views.calculate_period_view, name='calculate'),
    
    # MoySklad API endpoints
    path('api/moysklad/test-token/', views.moysklad_test_connection, name='ms_test_token'),
    path('api/moysklad/save-config/', views.moysklad_save_config, name='ms_save_config'),
    path('api/moysklad/sync-employees/', views.moysklad_sync_employees, name='ms_sync_employees'),
    path('api/moysklad/sync-facts/', views.moysklad_sync_facts, name='ms_sync_facts'),
    path('api/moysklad/close-month/', views.moysklad_close_month, name='ms_close_month'),
]
