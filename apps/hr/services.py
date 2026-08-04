"""
Geriye dönük uyumluluk servis katmanı.

Yeni kodlarda apps.hr.service_layer altındaki alan bazlı modüller
kullanılabilir. Mevcut view, test ve seed importları bu dosya üzerinden
çalışmaya devam eder.
"""

from .service_layer import (
    withdraw_job_application,
    reject_job_application,
    open_job_requisition,
    move_application_stage,
    create_recruitment_event,
    create_job_application,
    update_employee_goal_progress,
    submit_self_review,
    start_self_review,
    create_performance_review_event,
    create_performance_review,
    complete_performance_review,
    cancel_performance_review,
    approve_absence_request,
    approve_attendance_record,
    cancel_absence_request,
    change_employee_assignment,
    clock_in_attendance,
    clock_out_attendance,
    create_absence_request_event,
    create_attendance_event,
    generate_attendance_record,
    get_locked_absence_balance,
    get_scheduled_datetime,
    reject_absence_request,
    reject_attendance_record,
    submit_absence_request,
    submit_attendance_record,
    validate_absence_request_balance,
)

__all__ = [
    "withdraw_job_application",

    "reject_job_application",

    "open_job_requisition",

    "move_application_stage",

    "create_recruitment_event",

    "create_job_application",

    "update_employee_goal_progress",

    "submit_self_review",

    "start_self_review",

    "create_performance_review_event",

    "create_performance_review",

    "complete_performance_review",

    "cancel_performance_review",

    "approve_absence_request",
    "approve_attendance_record",
    "cancel_absence_request",
    "change_employee_assignment",
    "clock_in_attendance",
    "clock_out_attendance",
    "create_absence_request_event",
    "create_attendance_event",
    "generate_attendance_record",
    "get_locked_absence_balance",
    "get_scheduled_datetime",
    "reject_absence_request",
    "reject_attendance_record",
    "submit_absence_request",
    "submit_attendance_record",
    "validate_absence_request_balance",
]
