from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseForbidden
from django.core.exceptions import ValidationError

from apps.accounts.models import OrganizationMembership
from apps.organizations.models import Department

from .models import Employee, EmploymentAssignment, Position
from .forms import (
    AssignmentChangeForm,
    EmployeeForm,
    InitialAssignmentForm,
    PositionForm,
)
from .services import change_employee_assignment


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
def can_manage_hr(membership):
    return (
        has_hr_access(membership)
        and membership.can_manage_members
    )


def hr_management_forbidden():
    return HttpResponseForbidden(
        "İK kayıtlarını yönetme yetkiniz bulunmuyor."
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
            "can_manage_hr": can_manage_hr(membership),
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
            "can_manage_hr": can_manage_hr(membership),
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
    assignment_events = (
        employee.assignment_events
        .select_related(
            "previous_assignment",
            "previous_assignment__position",
            "previous_assignment__department",
            "new_assignment",
            "new_assignment__position",
            "new_assignment__department",
            "changed_by",
        )
        .order_by(
            "-effective_date",
            "-created_at",
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
            "can_manage_hr": can_manage_hr(membership),
            "assignment_events": assignment_events,
        },
    )
@login_required
def employee_create(request):
    membership = get_active_membership(request.user)

    if not can_manage_hr(membership):
        return hr_management_forbidden()

    company = membership.company

    if request.method == "POST":
        employee_form = EmployeeForm(
            request.POST,
            company=company,
            prefix="employee",
        )
        assignment_form = InitialAssignmentForm(
            request.POST,
            company=company,
            prefix="assignment",
        )

        if (
            employee_form.is_valid()
            and assignment_form.is_valid()
        ):
            with transaction.atomic():
                employee = employee_form.save(commit=False)
                employee.company = company
                employee.save()

                assignment = assignment_form.save(commit=False)
                assignment.employee = employee
                assignment.is_primary = True
                assignment.end_date = None
                assignment.save()

            messages.success(
                request,
                (
                    f"{employee.full_name} için personel kartı "
                    "ve ilk çalışma ataması oluşturuldu."
                ),
            )

            return redirect(
                "hr:employee_detail",
                employee_id=employee.id,
            )
    else:
        employee_form = EmployeeForm(
            company=company,
            prefix="employee",
        )
        assignment_form = InitialAssignmentForm(
            company=company,
            prefix="assignment",
            initial={
                "branch": membership.branch,
                "department": membership.department,
                "start_date": timezone.localdate(),
            },
        )

    return render(
        request,
        "hr/employee_form.html",
        {
            "current_membership": membership,
            "employee_form": employee_form,
            "assignment_form": assignment_form,
            "is_create": True,
        },
    )


@login_required
def employee_update(request, employee_id):
    membership = get_active_membership(request.user)

    if not can_manage_hr(membership):
        return hr_management_forbidden()

    employee = get_object_or_404(
        Employee,
        id=employee_id,
        company=membership.company,
    )

    if request.method == "POST":
        form = EmployeeForm(
            request.POST,
            instance=employee,
            company=membership.company,
        )

        if form.is_valid():
            with transaction.atomic():
                employee = form.save()

                if (
                    employee.employment_status
                    == Employee.EmploymentStatus.TERMINATED
                    and employee.termination_date
                ):
                    active_assignments = (
                        employee.assignments.filter(
                            end_date__isnull=True,
                        )
                    )

                    for assignment in active_assignments:
                        assignment.end_date = (
                            employee.termination_date
                        )
                        assignment.save()

            messages.success(
                request,
                (
                    f"{employee.full_name} personel kartı "
                    "güncellendi."
                ),
            )

            return redirect(
                "hr:employee_detail",
                employee_id=employee.id,
            )
    else:
        form = EmployeeForm(
            instance=employee,
            company=membership.company,
        )

    return render(
        request,
        "hr/employee_form.html",
        {
            "current_membership": membership,
            "employee": employee,
            "employee_form": form,
            "assignment_form": None,
            "is_create": False,
        },
    )


@login_required
def position_list(request):
    membership = get_active_membership(request.user)

    if not has_hr_access(membership):
        return redirect("hr:home")

    positions = (
        Position.objects.filter(
            company=membership.company,
        )
        .select_related(
            "department",
            "department__branch",
        )
        .annotate(
            active_assignment_count=Count(
                "employee_assignments",
                filter=Q(
                    employee_assignments__end_date__isnull=True,
                ),
                distinct=True,
            ),
        )
        .order_by(
            "department__name",
            "title",
        )
    )

    return render(
        request,
        "hr/position_list.html",
        {
            "current_membership": membership,
            "positions": positions,
            "can_manage_hr": can_manage_hr(membership),
        },
    )


@login_required
def position_create(request):
    membership = get_active_membership(request.user)

    if not can_manage_hr(membership):
        return hr_management_forbidden()

    if request.method == "POST":
        form = PositionForm(
            request.POST,
            company=membership.company,
        )

        if form.is_valid():
            position = form.save(commit=False)
            position.company = membership.company
            position.save()

            messages.success(
                request,
                (
                    f"{position.title} pozisyonu oluşturuldu."
                ),
            )

            return redirect("hr:position_list")
    else:
        form = PositionForm(
            company=membership.company,
        )

    return render(
        request,
        "hr/position_form.html",
        {
            "current_membership": membership,
            "form": form,
            "position": None,
        },
    )


@login_required
def position_update(request, position_id):
    membership = get_active_membership(request.user)

    if not can_manage_hr(membership):
        return hr_management_forbidden()

    position = get_object_or_404(
        Position,
        id=position_id,
        company=membership.company,
    )

    if request.method == "POST":
        form = PositionForm(
            request.POST,
            instance=position,
            company=membership.company,
        )

        if form.is_valid():
            position = form.save()

            messages.success(
                request,
                f"{position.title} pozisyonu güncellendi.",
            )

            return redirect("hr:position_list")
    else:
        form = PositionForm(
            instance=position,
            company=membership.company,
        )

    return render(
        request,
        "hr/position_form.html",
        {
            "current_membership": membership,
            "form": form,
            "position": position,
        },
    )
@login_required
def employee_assignment_change(request, employee_id):
    membership = get_active_membership(request.user)

    if not can_manage_hr(membership):
        return hr_management_forbidden()

    employee = get_object_or_404(
        Employee,
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
        )
        .filter(
            is_primary=True,
            end_date__isnull=True,
        )
        .first()
    )

    if not current_assignment:
        messages.error(
            request,
            (
                "Personelin değiştirilebilecek aktif "
                "birincil ataması bulunmuyor."
            ),
        )

        return redirect(
            "hr:employee_detail",
            employee_id=employee.id,
        )

    if request.method == "POST":
        form = AssignmentChangeForm(
            request.POST,
            company=membership.company,
            employee=employee,
            current_assignment=current_assignment,
        )

        if form.is_valid():
            try:
                new_assignment = change_employee_assignment(
                    employee=employee,
                    branch=form.cleaned_data["branch"],
                    department=form.cleaned_data["department"],
                    position=form.cleaned_data["position"],
                    manager=form.cleaned_data["manager"],
                    employment_type=(
                        form.cleaned_data["employment_type"]
                    ),
                    effective_date=(
                        form.cleaned_data["effective_date"]
                    ),
                    is_department_manager=(
                        form.cleaned_data[
                            "is_department_manager"
                        ]
                    ),
                    changed_by=request.user,
                    change_reason=(
                        form.cleaned_data["change_reason"]
                    ),
                )
            except ValidationError as error:
                form.add_error(
                    None,
                    error.messages,
                )
            else:
                messages.success(
                    request,
                    (
                        f"{employee.full_name} için "
                        f"{new_assignment.position.title} "
                        "ataması oluşturuldu. Önceki atama "
                        "çalışma geçmişinde korundu."
                    ),
                )

                return redirect(
                    "hr:employee_detail",
                    employee_id=employee.id,
                )
    else:
        form = AssignmentChangeForm(
            company=membership.company,
            employee=employee,
            current_assignment=current_assignment,
            initial={
                "branch": current_assignment.branch,
                "department": current_assignment.department,
                "position": current_assignment.position,
                "manager": current_assignment.manager,
                "employment_type": (
                    current_assignment.employment_type
                ),
                "effective_date": timezone.localdate(),
                "is_department_manager": (
                    current_assignment.is_department_manager
                ),
            },
        )

    return render(
        request,
        "hr/assignment_change_form.html",
        {
            "current_membership": membership,
            "employee": employee,
            "current_assignment": current_assignment,
            "form": form,
        },
    )