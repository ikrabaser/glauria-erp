from django.urls import path

from .views import (
    employee_create,
    employee_detail,
    employee_list,
    employee_update,
    home,
    position_create,
    position_list,
    position_update,
    employee_assignment_change,
)

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
    path(
        "personeller/<uuid:employee_id>/atama-degistir/",
        employee_assignment_change,
        name="employee_assignment_change",
    ),
    path(
        "personeller/yeni/",
        employee_create,
        name="employee_create",
    ),
    path(
        "personeller/<uuid:employee_id>/duzenle/",
        employee_update,
        name="employee_update",
    ),
    path(
        "pozisyonlar/",
        position_list,
        name="position_list",
    ),
    path(
        "pozisyonlar/yeni/",
        position_create,
        name="position_create",
    ),
    path(
        "pozisyonlar/<uuid:position_id>/duzenle/",
        position_update,
        name="position_update",
    ),
]