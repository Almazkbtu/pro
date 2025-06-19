from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

app_name = 'parking'

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='parking:home'), name='logout'),
    path('', views.home, name='home'),
    path('reserve/', views.reserve, name='reserve'),
    path('pay/', views.pay, name='pay'),
    path('daily-report/', views.daily_report, name='daily_report'),
    path('monthly-report/', views.monthly_report, name='monthly_report'),
    path('control-barrier/', views.control_barrier, name='control_barrier'),
] 