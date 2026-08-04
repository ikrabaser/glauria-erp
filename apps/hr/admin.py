from django.contrib import admin

from .models import (
    AbsenceBalance,
    AbsenceRequest,
    AbsenceRequestEvent,
    AbsenceType,
    AttendanceRecord,
    Employee,
    EmployeeScheduleAssignment,
    EmploymentAssignment,
    EmploymentAssignmentEvent,
    Position,
    WorkSchedule,
    WorkScheduleDay,
    AttendanceRecordEvent,
)


class EmploymentAssignmentInline(admin.TabularInline):
    model = EmploymentAssignment
    fk_name = "employee"
    extra = 0
    fields = (
        "branch",
        "department",
        "position",
        "manager",
        "employment_type",
        "start_date",
        "end_date",
        "is_primary",
        "is_department_manager",
    )
    show_change_link = True


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "title",
        "company",
        "department",
        "is_active",
    )
    list_filter = (
        "company",
        "department",
        "is_active",
    )
    search_fields = (
        "code",
        "title",
        "department__name",
        "company__name",
    )
    ordering = (
        "company__name",
        "department__name",
        "title",
    )
    list_select_related = (
        "company",
        "department",
        "department__branch",
    )


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "employee_number",
        "full_name_display",
        "company",
        "employment_status",
        "hire_date",
        "is_active",
    )
    list_filter = (
        "company",
        "employment_status",
        "is_active",
        "hire_date",
    )
    search_fields = (
        "employee_number",
        "first_name",
        "last_name",
        "preferred_name",
        "work_email",
        "personal_email",
        "user__username",
        "user__email",
    )
    ordering = (
        "company__name",
        "last_name",
        "first_name",
    )
    list_select_related = (
        "company",
        "user",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "deleted_at",
    )
    inlines = (
        EmploymentAssignmentInline,
    )

    @admin.display(description="Personel")
    def full_name_display(self, obj):
        return obj.full_name


@admin.register(EmploymentAssignment)
class EmploymentAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "position",
        "department",
        "manager",
        "employment_type",
        "start_date",
        "end_date",
        "is_primary",
        "is_department_manager",
    )
    list_filter = (
        "branch",
        "department",
        "employment_type",
        "is_primary",
        "is_department_manager",
        "start_date",
    )
    search_fields = (
        "employee__employee_number",
        "employee__first_name",
        "employee__last_name",
        "position__code",
        "position__title",
        "manager__first_name",
        "manager__last_name",
    )
    ordering = (
        "-is_primary",
        "-start_date",
    )
    list_select_related = (
        "employee",
        "branch",
        "department",
        "position",
        "manager",
    )

@admin.register(EmploymentAssignmentEvent)
class EmploymentAssignmentEventAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "event_type",
        "effective_date",
        "previous_assignment",
        "new_assignment",
        "changed_by",
    )
    list_filter = (
        "company",
        "event_type",
        "effective_date",
    )
    search_fields = (
        "employee__employee_number",
        "employee__first_name",
        "employee__last_name",
        "reason",
        "changed_by__username",
    )
    ordering = (
        "-effective_date",
        "-created_at",
    )
    list_select_related = (
        "company",
        "employee",
        "previous_assignment",
        "new_assignment",
        "changed_by",
    )
    readonly_fields = (
        "company",
        "employee",
        "previous_assignment",
        "new_assignment",
        "changed_by",
        "event_type",
        "effective_date",
        "reason",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False
@admin.register(AbsenceType)
class AbsenceTypeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "company",
        "default_entitlement_days",
        "is_paid",
        "requires_approval",
        "deducts_balance",
        "is_active",
    )
    list_filter = (
        "company",
        "is_paid",
        "requires_approval",
        "deducts_balance",
        "is_active",
    )
    search_fields = (
        "code",
        "name",
        "company__name",
    )
    ordering = (
        "company__name",
        "name",
    )
    list_select_related = (
        "company",
    )


@admin.register(AbsenceBalance)
class AbsenceBalanceAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "absence_type",
        "year",
        "entitled_days",
        "carried_days",
        "adjustment_days",
        "used_days",
        "available_days_display",
    )
    list_filter = (
        "company",
        "absence_type",
        "year",
    )
    search_fields = (
        "employee__employee_number",
        "employee__first_name",
        "employee__last_name",
        "absence_type__code",
        "absence_type__name",
    )
    ordering = (
        "-year",
        "employee__last_name",
        "employee__first_name",
    )
    list_select_related = (
        "company",
        "employee",
        "absence_type",
    )

    @admin.display(description="Kalan gün")
    def available_days_display(self, obj):
        return obj.available_days


@admin.register(AbsenceRequest)
class AbsenceRequestAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "absence_type",
        "start_date",
        "end_date",
        "requested_days",
        "status",
        "decided_by",
    )
    list_filter = (
        "company",
        "absence_type",
        "status",
        "start_date",
    )
    search_fields = (
        "employee__employee_number",
        "employee__first_name",
        "employee__last_name",
        "absence_type__code",
        "absence_type__name",
        "reason",
    )
    ordering = (
        "-start_date",
        "-created_at",
    )
    list_select_related = (
        "company",
        "employee",
        "absence_type",
        "decided_by",
    )
    readonly_fields = (
        "requested_days",
        "submitted_at",
        "decided_at",
        "decided_by",
        "created_at",
        "updated_at",
    )


@admin.register(AbsenceRequestEvent)
class AbsenceRequestEventAdmin(admin.ModelAdmin):
    list_display = (
        "request",
        "previous_status",
        "new_status",
        "changed_by",
        "created_at",
    )
    list_filter = (
        "company",
        "new_status",
        "created_at",
    )
    search_fields = (
        "request__employee__employee_number",
        "request__employee__first_name",
        "request__employee__last_name",
        "note",
        "changed_by__username",
    )
    ordering = (
        "-created_at",
    )
    list_select_related = (
        "request",
        "request__employee",
        "company",
        "changed_by",
    )
    readonly_fields = (
        "request",
        "company",
        "previous_status",
        "new_status",
        "changed_by",
        "note",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False
class WorkScheduleDayInline(admin.TabularInline):
    model = WorkScheduleDay
    extra = 0
    fields = (
        "weekday",
        "is_working_day",
        "start_time",
        "end_time",
        "break_minutes",
        "crosses_midnight",
    )
    ordering = (
        "weekday",
    )


@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "company",
        "weekly_hours",
        "timezone_name",
        "is_active",
    )
    list_filter = (
        "company",
        "is_active",
    )
    search_fields = (
        "code",
        "name",
        "company__name",
    )
    ordering = (
        "company__name",
        "name",
    )
    list_select_related = (
        "company",
    )
    inlines = (
        WorkScheduleDayInline,
    )


@admin.register(WorkScheduleDay)
class WorkScheduleDayAdmin(admin.ModelAdmin):
    list_display = (
        "work_schedule",
        "weekday",
        "is_working_day",
        "start_time",
        "end_time",
        "break_minutes",
        "crosses_midnight",
    )
    list_filter = (
        "work_schedule__company",
        "work_schedule",
        "is_working_day",
        "weekday",
    )
    search_fields = (
        "work_schedule__code",
        "work_schedule__name",
        "work_schedule__company__name",
    )
    ordering = (
        "work_schedule__company__name",
        "work_schedule__name",
        "weekday",
    )
    list_select_related = (
        "work_schedule",
        "work_schedule__company",
    )


@admin.register(EmployeeScheduleAssignment)
class EmployeeScheduleAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "work_schedule",
        "company",
        "start_date",
        "end_date",
        "is_primary",
    )
    list_filter = (
        "company",
        "work_schedule",
        "is_primary",
        "start_date",
        "end_date",
    )
    search_fields = (
        "employee__employee_number",
        "employee__first_name",
        "employee__last_name",
        "work_schedule__code",
        "work_schedule__name",
    )
    ordering = (
        "-start_date",
        "employee__last_name",
        "employee__first_name",
    )
    list_select_related = (
        "company",
        "employee",
        "work_schedule",
    )


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "work_date",
        "status",
        "clock_in_at",
        "clock_out_at",
        "worked_minutes",
        "late_minutes",
        "overtime_minutes",
        "approval_status",
    )
    list_filter = (
        "company",
        "status",
        "approval_status",
        "source",
        "work_date",
    )
    search_fields = (
        "employee__employee_number",
        "employee__first_name",
        "employee__last_name",
        "note",
    )
    ordering = (
        "-work_date",
        "employee__last_name",
        "employee__first_name",
    )
    list_select_related = (
        "company",
        "employee",
        "schedule_assignment",
        "approved_by",
    )
    readonly_fields = (
        "worked_minutes",
        "approved_at",
        "created_at",
        "updated_at",
    )
@admin.register(AttendanceRecordEvent)
class AttendanceRecordEventAdmin(admin.ModelAdmin):
    list_display = (
        "record",
        "event_type",
        "previous_approval_status",
        "new_approval_status",
        "changed_by",
        "occurred_at",
    )
    list_filter = (
        "company",
        "event_type",
        "new_approval_status",
        "occurred_at",
    )
    search_fields = (
        "record__employee__employee_number",
        "record__employee__first_name",
        "record__employee__last_name",
        "note",
        "changed_by__username",
    )
    ordering = (
        "-occurred_at",
        "-created_at",
    )
    list_select_related = (
        "record",
        "record__employee",
        "company",
        "changed_by",
    )
    readonly_fields = (
        "record",
        "company",
        "event_type",
        "previous_approval_status",
        "new_approval_status",
        "changed_by",
        "note",
        "occurred_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False