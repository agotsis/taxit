from django.urls import path
from . import views

urlpatterns = [
    path("", views.year_view, name="home"),
    path("year/<int:year>/", views.year_view, name="year_view"),
    path("year/<int:year>/month/<int:month>/", views.year_view, name="year_month_view"),
    path("bulk-edit/", views.day_bulk_edit, name="day_bulk_edit"),
    path("offices/", views.office_list, name="office_list"),
    path("states/", views.state_list, name="state_list"),
    path("states/<str:abbreviation>/toggle/", views.state_toggle, name="state_toggle"),
    path("ratio-views/", views.ratio_view_list, name="ratio_view_list"),
    path(
        "ratio-views/<int:pk>/toggle-hidden/",
        views.ratio_view_toggle_hidden,
        name="ratio_view_toggle_hidden",
    ),
    path("ratio-views/<int:pk>/", views.ratio_view_detail, name="ratio_view_detail"),
    path(
        "ratio-views/<int:pk>/copy/",
        views.ratio_view_copy,
        name="ratio_view_copy",
    ),
    path(
        "ratio-views/<int:pk>/month/<int:month>/year/<int:year>/",
        views.ratio_view_detail,
        name="ratio_view_month_detail",
    ),
    path("day/<str:date_str>/json/", views.day_json, name="day_json"),
    path("day/<str:date_str>/update/", views.day_update, name="day_update"),
    path("day/<str:date_str>/delete/", views.day_delete, name="day_delete"),
]
