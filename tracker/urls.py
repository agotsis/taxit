from django.urls import path
from . import views

urlpatterns = [
    path('', views.year_view, name='year_view'),
    path('year/<int:year>/', views.year_view, name='year_view'),
    path('bulk-edit/', views.day_bulk_edit, name='day_bulk_edit'),
    path('offices/', views.office_list, name='office_list'),
    path('ratio-views/', views.ratio_view_list, name='ratio_view_list'),
    path('ratio-views/<int:pk>/', views.ratio_view_detail, name='ratio_view_detail'),
]
