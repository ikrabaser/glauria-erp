from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import OrganizationMembership
from apps.organizations.models import Department

from .models import Employee, EmploymentAssignment, Position


def get_active_membership(user):
    return (
        user.organization_memberships
        .select_related(
            "company",
            "branch",
            "department",
        )
        .filter(is_active=True)
        .order_by("-is_primary", "created_at")
        .first()
    )


def has_hr_access(membership):
    return (
        membership
        and membership.has_module_access(
            OrganizationMembership.Module.HR
        )
    )


def current_assignment_queryset():
    return (
        EmploymentAssignment.objects
        .filter(
            is_primary=True,
            end_date__isnull=True,
        )
        .select_related(
            "branch",
            "department",
            "position",
            "manager",
            "manager__user",
        )
    )


@login_required
def home(request):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("dashboard:home")

    if not has_hr_access(membership):
        return render(
            request,
            "hr/home.html",
            {
                "current_membership": membership,
                "can_access_hr": False,
            },
        )

    company = membership.company
    today = timezone.localdate()
    new_hire_threshold = today - timedelta(days=90)

    employees = Employee.objects.filter(
        company=company,
        is_active=True,
    )

    active_assignments = EmploymentAssignment.objects.filter(
        employee__company=company,
        employee__is_active=True,
        is_primary=True,
        end_date__isnull=True,
    )

    department_manager_assignments = (
        current_assignment_queryset()
        .filter(
            employee__company=company,
            employee__is_active=True,
            is_department_manager=True,
        )
    )

    departments = (
        Department.objects.filter(
            branch__company=company,
            is_active=True,
        )
        .select_related(
            "branch",
        )
        .annotate(
            active_employee_count=Count(
                "employee_assignments",
                filter=Q(
                    employee_assignments__employee__company=company,
                    employee_assignments__employee__is_active=True,
                    employee_assignments__is_primary=True,
                    employee_assignments__end_date__isnull=True,
                ),
                distinct=True,
            ),
        )
        .prefetch_related(
            Prefetch(
                "employee_assignments",
                queryset=department_manager_assignments,
                to_attr="active_manager_assignments",
            ),
        )
        .order_by(
            "branch__name",
            "name",
        )
    )

    recent_employees = (
        employees
        .filter(
            hire_date__gte=new_hire_threshold,
        )
        .prefetch_related(
            Prefetch(
                "assignments",
                queryset=current_assignment_queryset(),
                to_attr="current_assignments",
            ),
        )
        .order_by(
            "-hire_date",
            "last_name",
        )[:5]
    )

    return render(
        request,
        "hr/home.html",
        {
            "current_membership": membership,
            "can_access_hr": True,
            "total_employee_count": employees.count(),
            "active_employee_count": employees.filter(
                employment_status=Employee.EmploymentStatus.ACTIVE,
            ).count(),
            "on_leave_employee_count": employees.filter(
                employment_status=Employee.EmploymentStatus.ON_LEAVE,
            ).count(),
            "position_count": Position.objects.filter(
                company=company,
                is_active=True,
            ).count(),
            "active_assignment_count": active_assignments.count(),
            "department_manager_count": (
                department_manager_assignments.count()
            ),
            "departments": departments,
            "recent_employees": recent_employees,
        },
    )


@login_required
def employee_list(request):
    membership = get_active_membership(request.user)

    if not has_hr_access(membership):
        return redirect("hr:home")

    company = membership.company
    search_query = request.GET.get("q", "").strip()
    department_id = request.GET.get("department", "").strip()
    status = request.GET.get("status", "").strip()

    employees = (
        Employee.objects.filter(
            company=company,
        )
        .select_related(
            "company",
            "user",
        )
        .prefetch_related(
            Prefetch(
                "assignments",
                queryset=current_assignment_queryset(),
                to_attr="current_assignments",
            ),
        )
        .order_by(
            "last_name",
            "first_name",
        )
    )

    if search_query:
        employees = employees.filter(
            Q(employee_number__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(preferred_name__icontains=search_query)
            | Q(work_email__icontains=search_query)
            | Q(
                assignments__position__title__icontains=(
                    search_query
                )
            )
            | Q(
                assignments__department__name__icontains=(
                    search_query
                )
            )
        ).distinct()

    if department_id:
        employees = employees.filter(
            assignments__department_id=department_id,
            assignments__is_primary=True,
            assignments__end_date__isnull=True,
        ).distinct()

    valid_statuses = {
        value
        for value, _ in Employee.EmploymentStatus.choices
    }

    if status in valid_statuses:
        employees = employees.filter(
            employment_status=status,
        )
    else:
        status = ""

    departments = Department.objects.filter(
        branch__company=company,
        is_active=True,
    ).select_related(
        "branch",
    ).order_by(
        "branch__name",
        "name",
    )

    return render(
        request,
        "hr/employee_list.html",
        {
            "current_membership": membership,
            "employees": employees,
            "departments": departments,
            "employment_status_choices": (
                Employee.EmploymentStatus.choices
            ),
            "search_query": search_query,
            "selected_department": department_id,
            "selected_status": status,
        },
    )


@login_required
def employee_detail(request, employee_id):
    membership = get_active_membership(request.user)

    if not has_hr_access(membership):
        return redirect("hr:home")

    employee = get_object_or_404(
        Employee.objects.select_related(
            "company",
            "user",
        ),
        id=employee_id,
        company=membership.company,
    )

    current_assignment = (
        employee.assignments
        .select_related(
            "branch",
            "department",
            "position",
            "manager",
            "manager__user",
        )
        .filter(
            is_primary=True,
            end_date__isnull=True,
        )
        .first()
    )

    assignment_history = (
        employee.assignments
        .select_related(
            "branch",
            "department",
            "position",
            "manager",
        )
        .order_by(
            "-start_date",
            "-created_at",
        )
    )

    direct_reports = (
        EmploymentAssignment.objects
        .filter(
            manager=employee,
            employee__company=membership.company,
            employee__is_active=True,
            is_primary=True,
            end_date__isnull=True,
        )
        .select_related(
            "employee",
            "employee__user",
            "department",
            "position",
        )
        .order_by(
            "employee__last_name",
            "employee__first_name",
        )
    )

    return render(
        request,
        "hr/employee_detail.html",
        {
            "current_membership": membership,
            "employee": employee,
            "current_assignment": current_assignment,
            "assignment_history": assignment_history,
            "direct_reports": direct_reports,
        },
    )