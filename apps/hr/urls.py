from django.urls import path

from .views import employee_detail, employee_list, home


app_name = "hr"

urlpatterns = [
    path(
        "",
        home,
        name="home",
    ),
    path(
        "personeller/",
        employee_list,
        name="employee_list",
    ),
    path(
        "personeller/<uuid:employee_id>/",
        employee_detail,
        name="employee_detail",
    ),
]