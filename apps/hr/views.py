from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseForbidden
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST

from apps.accounts.models import OrganizationMembership
from apps.organizations.models import Department

from .models import (
    AbsenceBalance,
    AbsenceRequest,
    AbsenceType,
    Employee,
    EmploymentAssignment,
    Position,
    EmployeeGoal,
    PerformanceReview,
    PerformanceReviewCycle,
    Candidate,
    JobApplication,
    JobRequisition,
    RecruitmentAIAssessment,
)
from .forms import (
    AbsenceCancellationForm,
    AbsenceDecisionForm,
    AbsenceRequestForm,
    AssignmentChangeForm,
    DepartmentForm,
    EmployeeForm,
    InitialAssignmentForm,
    PositionForm,
    JobRequisitionForm,
    CandidateForm,
)
from .services import (
    approve_absence_request,
    cancel_absence_request,
    change_employee_assignment,
    reject_absence_request,
    submit_absence_request,
    open_job_requisition,
)

from .service_layer import (
    build_candidate_application_ai_context,
    queue_recruitment_ai_assessment,
)

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
def get_current_employee(user, company):
    return (
        Employee.objects
        .filter(
            company=company,
            user=user,
            is_active=True,
        )
        .select_related(
            "company",
            "user",
        )
        .first()
    )


def can_access_absence_management(
    membership,
    employee,
):
    return bool(
        membership
        and (
            employee
            or can_manage_hr(membership)
        )
    )


def absence_access_forbidden():
    return HttpResponseForbidden(
        "İzin ve devamsızlık kayıtlarına erişim yetkiniz bulunmuyor."
    )


def visible_absence_requests(
    *,
    membership,
    employee,
):
    requests = (
        AbsenceRequest.objects
        .filter(company=membership.company)
        .select_related(
            "employee",
            "employee__user",
            "absence_type",
            "decided_by",
        )
        .prefetch_related("events")
    )

    if can_manage_hr(membership):
        return requests

    if not employee:
        return requests.none()

    direct_report_ids = (
        EmploymentAssignment.objects.filter(
            manager=employee,
            is_primary=True,
            end_date__isnull=True,
            employee__is_active=True,
        )
        .values_list(
            "employee_id",
            flat=True,
        )
    )

    return requests.filter(
        Q(employee=employee)
        | Q(employee_id__in=direct_report_ids)
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
@login_required
def department_list(request):
    membership = get_active_membership(request.user)

    if not membership or not has_hr_access(membership):
        return hr_management_forbidden()

    company = membership.company
    search_query = request.GET.get("q", "").strip()
    branch_id = request.GET.get("branch", "").strip()
    status = request.GET.get("status", "").strip()

    manager_assignments = (
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
        )
        .select_related(
            "branch",
            "parent",
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
            active_position_count=Count(
                "hr_positions",
                filter=Q(
                    hr_positions__company=company,
                    hr_positions__is_active=True,
                ),
                distinct=True,
            ),
        )
        .prefetch_related(
            Prefetch(
                "employee_assignments",
                queryset=manager_assignments,
                to_attr="active_manager_assignments",
            ),
        )
    )

    if search_query:
        departments = departments.filter(
            Q(name__icontains=search_query)
            | Q(code__icontains=search_query)
            | Q(branch__name__icontains=search_query)
        )

    if branch_id:
        departments = departments.filter(
            branch_id=branch_id,
        )

    if status == "active":
        departments = departments.filter(is_active=True)
    elif status == "inactive":
        departments = departments.filter(is_active=False)

    departments = departments.order_by(
        "branch__name",
        "name",
    )

    branches = (
        membership.company.branches
        .filter(is_active=True)
        .order_by("name")
    )

    return render(
        request,
        "hr/department_list.html",
        {
            "current_membership": membership,
            "can_access_hr": True,
            "can_manage_hr": can_manage_hr(membership),
            "departments": departments,
            "branches": branches,
            "search_query": search_query,
            "selected_branch": branch_id,
            "selected_status": status,
        },
    )


@login_required
def department_detail(request, department_id):
    membership = get_active_membership(request.user)

    if not membership or not has_hr_access(membership):
        return hr_management_forbidden()

    company = membership.company

    manager_assignments = (
        current_assignment_queryset()
        .filter(
            employee__company=company,
            employee__is_active=True,
            is_department_manager=True,
        )
    )

    department = get_object_or_404(
        Department.objects
        .select_related(
            "branch",
            "parent",
        )
        .prefetch_related(
            Prefetch(
                "employee_assignments",
                queryset=manager_assignments,
                to_attr="active_manager_assignments",
            ),
        ),
        pk=department_id,
        branch__company=company,
    )

    active_assignments = (
        current_assignment_queryset()
        .filter(
            employee__company=company,
            employee__is_active=True,
            department=department,
        )
        .order_by(
            "-is_department_manager",
            "employee__last_name",
            "employee__first_name",
        )
    )

    positions = (
        Position.objects.filter(
            company=company,
            department=department,
        )
        .annotate(
            active_assignment_count=Count(
                "employee_assignments",
                filter=Q(
                    employee_assignments__is_primary=True,
                    employee_assignments__end_date__isnull=True,
                    employee_assignments__employee__is_active=True,
                ),
                distinct=True,
            ),
        )
        .order_by(
            "-is_active",
            "title",
        )
    )

    sub_departments = (
        Department.objects.filter(
            branch__company=company,
            parent=department,
        )
        .select_related("branch")
        .order_by(
            "-is_active",
            "name",
        )
    )

    manager_assignment = None

    if department.active_manager_assignments:
        manager_assignment = (
            department.active_manager_assignments[0]
        )

    return render(
        request,
        "hr/department_detail.html",
        {
            "current_membership": membership,
            "can_access_hr": True,
            "can_manage_hr": can_manage_hr(membership),
            "department": department,
            "manager_assignment": manager_assignment,
            "active_assignments": active_assignments,
            "positions": positions,
            "sub_departments": sub_departments,
        },
    )


@login_required
def department_create(request):
    membership = get_active_membership(request.user)

    if not membership or not can_manage_hr(membership):
        return hr_management_forbidden()

    if request.method == "POST":
        form = DepartmentForm(
            request.POST,
            company=membership.company,
        )

        if form.is_valid():
            department = form.save()

            messages.success(
                request,
                "Departman başarıyla oluşturuldu.",
            )

            return redirect(
                "hr:department_detail",
                department_id=department.id,
            )
    else:
        form = DepartmentForm(
            company=membership.company,
        )

    return render(
        request,
        "hr/department_form.html",
        {
            "current_membership": membership,
            "can_access_hr": True,
            "can_manage_hr": True,
            "form": form,
            "page_title": "Yeni Departman",
            "page_description": (
                "Şube ve üst departman bağlantısıyla yeni "
                "organizasyon birimi oluşturun."
            ),
            "submit_label": "Departman Oluştur",
        },
    )


@login_required
def department_update(request, department_id):
    membership = get_active_membership(request.user)

    if not membership or not can_manage_hr(membership):
        return hr_management_forbidden()

    department = get_object_or_404(
        Department,
        pk=department_id,
        branch__company=membership.company,
    )

    if request.method == "POST":
        form = DepartmentForm(
            request.POST,
            instance=department,
            company=membership.company,
        )

        if form.is_valid():
            department = form.save()

            messages.success(
                request,
                "Departman bilgileri güncellendi.",
            )

            return redirect(
                "hr:department_detail",
                department_id=department.id,
            )
    else:
        form = DepartmentForm(
            instance=department,
            company=membership.company,
        )

    return render(
        request,
        "hr/department_form.html",
        {
            "current_membership": membership,
            "can_access_hr": True,
            "can_manage_hr": True,
            "form": form,
            "department": department,
            "page_title": "Departmanı Düzenle",
            "page_description": (
                "Departman kodunu, şubesini ve organizasyon "
                "hiyerarşisini güncelleyin."
            ),
            "submit_label": "Değişiklikleri Kaydet",
        },
    )
@login_required
def absence_request_list(request):
    membership = get_active_membership(request.user)

    if not membership:
        return absence_access_forbidden()

    employee = get_current_employee(
        request.user,
        membership.company,
    )

    if not can_access_absence_management(
        membership,
        employee,
    ):
        return absence_access_forbidden()

    requests = visible_absence_requests(
        membership=membership,
        employee=employee,
    )

    search_query = request.GET.get("q", "").strip()
    selected_status = request.GET.get("status", "").strip()
    selected_type = request.GET.get("type", "").strip()
    selected_scope = request.GET.get("scope", "").strip()

    if search_query:
        requests = requests.filter(
            Q(employee__employee_number__icontains=search_query)
            | Q(employee__first_name__icontains=search_query)
            | Q(employee__last_name__icontains=search_query)
            | Q(absence_type__name__icontains=search_query)
            | Q(reason__icontains=search_query)
        )

    valid_statuses = {
        value
        for value, _ in AbsenceRequest.Status.choices
    }

    if selected_status in valid_statuses:
        requests = requests.filter(
            status=selected_status,
        )

    if selected_type:
        requests = requests.filter(
            absence_type_id=selected_type,
        )

    if selected_scope == "mine" and employee:
        requests = requests.filter(employee=employee)
    elif selected_scope == "team" and employee:
        direct_report_ids = (
            EmploymentAssignment.objects.filter(
                manager=employee,
                is_primary=True,
                end_date__isnull=True,
                employee__is_active=True,
            )
            .values_list(
                "employee_id",
                flat=True,
            )
        )
        requests = requests.filter(
            employee_id__in=direct_report_ids,
        )

    requests = requests.order_by(
        "-created_at",
    )

    current_year = timezone.localdate().year

    balances = (
        AbsenceBalance.objects.none()
    )

    if employee:
        balances = (
            AbsenceBalance.objects.filter(
                company=membership.company,
                employee=employee,
                year=current_year,
            )
            .select_related("absence_type")
            .order_by("absence_type__name")
        )

    absence_types = (
        AbsenceType.objects.filter(
            company=membership.company,
            is_active=True,
        )
        .order_by("name")
    )

    return render(
        request,
        "hr/absence_request_list.html",
        {
            "current_membership": membership,
            "current_employee": employee,
            "can_access_hr": has_hr_access(membership),
            "can_manage_hr": can_manage_hr(membership),
            "can_create_absence_request": bool(
                employee
                or can_manage_hr(membership)
            ),
            "absence_requests": requests,
            "absence_types": absence_types,
            "balances": balances,
            "status_choices": AbsenceRequest.Status.choices,
            "search_query": search_query,
            "selected_status": selected_status,
            "selected_type": selected_type,
            "selected_scope": selected_scope,
            "current_year": current_year,
        },
    )


@login_required
def absence_request_create(request):
    membership = get_active_membership(request.user)

    if not membership:
        return absence_access_forbidden()

    employee = get_current_employee(
        request.user,
        membership.company,
    )
    manage_all = can_manage_hr(membership)

    if not employee and not manage_all:
        return absence_access_forbidden()

    if request.method == "POST":
        form = AbsenceRequestForm(
            request.POST,
            company=membership.company,
            employee=employee,
            can_manage_all=manage_all,
        )

        if form.is_valid():
            try:
                with transaction.atomic():
                    absence_request = form.save(
                        commit=False,
                    )
                    absence_request.company = (
                        membership.company
                    )
                    absence_request.save()

                    if (
                        request.POST.get("submit_action")
                        == "submit"
                    ):
                        absence_request = (
                            submit_absence_request(
                                absence_request=absence_request,
                                changed_by=request.user,
                                note=(
                                    "Talep oluşturularak "
                                    "onaya gönderildi."
                                ),
                            )
                        )
            except ValidationError as error:
                form.add_error(
                    None,
                    error.messages,
                )
            else:
                if (
                    absence_request.status
                    == AbsenceRequest.Status.SUBMITTED
                ):
                    messages.success(
                        request,
                        "İzin talebi onaya gönderildi.",
                    )
                else:
                    messages.success(
                        request,
                        "İzin talebi taslak olarak kaydedildi.",
                    )

                return redirect(
                    "hr:absence_request_detail",
                    request_id=absence_request.id,
                )
    else:
        form = AbsenceRequestForm(
            company=membership.company,
            employee=employee,
            can_manage_all=manage_all,
        )

    return render(
        request,
        "hr/absence_request_form.html",
        {
            "current_membership": membership,
            "current_employee": employee,
            "can_access_hr": has_hr_access(membership),
            "can_manage_hr": manage_all,
            "form": form,
        },
    )


@login_required
def absence_request_detail(request, request_id):
    membership = get_active_membership(request.user)

    if not membership:
        return absence_access_forbidden()

    employee = get_current_employee(
        request.user,
        membership.company,
    )

    if not can_access_absence_management(
        membership,
        employee,
    ):
        return absence_access_forbidden()

    absence_request = get_object_or_404(
        visible_absence_requests(
            membership=membership,
            employee=employee,
        ),
        pk=request_id,
    )

    balance = (
        AbsenceBalance.objects.filter(
            company=membership.company,
            employee=absence_request.employee,
            absence_type=absence_request.absence_type,
            year=absence_request.start_date.year,
        )
        .first()
    )

    can_manage = can_manage_hr(membership)
    is_owner = bool(
        employee
        and absence_request.employee_id == employee.id
    )

    return render(
        request,
        "hr/absence_request_detail.html",
        {
            "current_membership": membership,
            "current_employee": employee,
            "can_access_hr": has_hr_access(membership),
            "can_manage_hr": can_manage,
            "absence_request": absence_request,
            "balance": balance,
            "events": absence_request.events.select_related(
                "changed_by",
            ),
            "can_submit": (
                absence_request.status
                == AbsenceRequest.Status.DRAFT
                and (
                    is_owner
                    or can_manage
                )
            ),
            "can_decide": (
                can_manage
                and absence_request.status
                == AbsenceRequest.Status.SUBMITTED
            ),
            "can_cancel": (
                (
                    is_owner
                    or can_manage
                )
                and absence_request.status
                in {
                    AbsenceRequest.Status.DRAFT,
                    AbsenceRequest.Status.SUBMITTED,
                    AbsenceRequest.Status.APPROVED,
                }
            ),
            "decision_form": AbsenceDecisionForm(),
            "cancellation_form": AbsenceCancellationForm(),
        },
    )


@login_required
def absence_request_submit(request, request_id):
    membership = get_active_membership(request.user)

    if not membership or request.method != "POST":
        return absence_access_forbidden()

    employee = get_current_employee(
        request.user,
        membership.company,
    )

    absence_request = get_object_or_404(
        AbsenceRequest,
        pk=request_id,
        company=membership.company,
    )

    is_owner = bool(
        employee
        and absence_request.employee_id == employee.id
    )

    if not is_owner and not can_manage_hr(membership):
        return absence_access_forbidden()

    try:
        submit_absence_request(
            absence_request=absence_request,
            changed_by=request.user,
            note="Taslak talep onaya gönderildi.",
        )
    except ValidationError as error:
        messages.error(
            request,
            " ".join(error.messages),
        )
    else:
        messages.success(
            request,
            "İzin talebi onaya gönderildi.",
        )

    return redirect(
        "hr:absence_request_detail",
        request_id=absence_request.id,
    )


@login_required
def absence_request_decide(request, request_id):
    membership = get_active_membership(request.user)

    if (
        not membership
        or not can_manage_hr(membership)
        or request.method != "POST"
    ):
        return absence_access_forbidden()

    absence_request = get_object_or_404(
        AbsenceRequest,
        pk=request_id,
        company=membership.company,
    )

    form = AbsenceDecisionForm(request.POST)

    if form.is_valid():
        action = form.cleaned_data["action"]
        decision_note = form.cleaned_data[
            "decision_note"
        ]

        try:
            if (
                action
                == AbsenceDecisionForm.Action.APPROVE
            ):
                approve_absence_request(
                    absence_request=absence_request,
                    changed_by=request.user,
                    decision_note=decision_note,
                )
                success_message = (
                    "İzin talebi onaylandı."
                )
            else:
                reject_absence_request(
                    absence_request=absence_request,
                    changed_by=request.user,
                    decision_note=decision_note,
                )
                success_message = (
                    "İzin talebi reddedildi."
                )
        except ValidationError as error:
            messages.error(
                request,
                " ".join(error.messages),
            )
        else:
            messages.success(
                request,
                success_message,
            )
    else:
        error_messages = []

        for errors in form.errors.values():
            error_messages.extend(errors)

        messages.error(
            request,
            " ".join(error_messages),
        )

    return redirect(
        "hr:absence_request_detail",
        request_id=absence_request.id,
    )


@login_required
def absence_request_cancel(request, request_id):
    membership = get_active_membership(request.user)

    if not membership or request.method != "POST":
        return absence_access_forbidden()

    employee = get_current_employee(
        request.user,
        membership.company,
    )

    absence_request = get_object_or_404(
        AbsenceRequest,
        pk=request_id,
        company=membership.company,
    )

    is_owner = bool(
        employee
        and absence_request.employee_id == employee.id
    )

    if not is_owner and not can_manage_hr(membership):
        return absence_access_forbidden()

    form = AbsenceCancellationForm(request.POST)

    if form.is_valid():
        try:
            cancel_absence_request(
                absence_request=absence_request,
                changed_by=request.user,
                note=form.cleaned_data[
                    "cancellation_note"
                ],
            )
        except ValidationError as error:
            messages.error(
                request,
                " ".join(error.messages),
            )
        else:
            messages.success(
                request,
                "İzin talebi iptal edildi.",
            )

    return redirect(
        "hr:absence_request_detail",
        request_id=absence_request.id,
    )


@login_required
def performance_dashboard(request):
    membership = get_active_membership(request.user)

    if not has_hr_access(membership):
        return redirect("hr:home")

    company = membership.company
    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()

    cycles = PerformanceReviewCycle.objects.filter(
        company=company,
        is_active=True,
    )

    active_cycle = (
        cycles.filter(
            status=PerformanceReviewCycle.Status.OPEN,
        )
        .order_by(
            "-start_date",
            "-created_at",
        )
        .first()
    )

    goals = (
        EmployeeGoal.objects.filter(
            company=company,
        )
        .select_related(
            "employee",
            "employee__user",
            "cycle",
        )
        .order_by(
            "-cycle__start_date",
            "employee__last_name",
            "employee__first_name",
            "due_date",
        )
    )

    reviews = (
        PerformanceReview.objects.filter(
            company=company,
        )
        .select_related(
            "employee",
            "employee__user",
            "manager",
            "manager__user",
            "cycle",
            "completed_by",
        )
        .order_by(
            "-cycle__start_date",
            "employee__last_name",
            "employee__first_name",
        )
    )

    if active_cycle:
        goals = goals.filter(cycle=active_cycle)
        reviews = reviews.filter(cycle=active_cycle)

    if search_query:
        reviews = reviews.filter(
            Q(employee__employee_number__icontains=search_query)
            | Q(employee__first_name__icontains=search_query)
            | Q(employee__last_name__icontains=search_query)
            | Q(manager__first_name__icontains=search_query)
            | Q(manager__last_name__icontains=search_query)
            | Q(cycle__name__icontains=search_query)
            | Q(cycle__code__icontains=search_query)
        )

    valid_statuses = {
        value
        for value, _label in PerformanceReview.Status.choices
    }

    if status_filter in valid_statuses:
        reviews = reviews.filter(status=status_filter)
    else:
        status_filter = ""

    review_counts = {
        "total": reviews.count(),
        "draft": reviews.filter(
            status=PerformanceReview.Status.DRAFT,
        ).count(),
        "self_review": reviews.filter(
            status=PerformanceReview.Status.SELF_REVIEW,
        ).count(),
        "manager_review": reviews.filter(
            status=PerformanceReview.Status.MANAGER_REVIEW,
        ).count(),
        "completed": reviews.filter(
            status=PerformanceReview.Status.COMPLETED,
        ).count(),
        "cancelled": reviews.filter(
            status=PerformanceReview.Status.CANCELLED,
        ).count(),
    }

    average_rating = (
        reviews.filter(
            status=PerformanceReview.Status.COMPLETED,
            overall_rating__isnull=False,
        )
        .aggregate(value=Avg("overall_rating"))
        .get("value")
    )

    goal_summary = goals.aggregate(
        average_progress=Avg("progress_percentage"),
    )

    return render(
        request,
        "hr/performance_dashboard.html",
        {
            "current_membership": membership,
            "active_cycle": active_cycle,
            "cycle_count": cycles.count(),
            "goals": goals[:8],
            "goal_count": goals.count(),
            "completed_goal_count": goals.filter(
                status=EmployeeGoal.Status.COMPLETED,
            ).count(),
            "average_goal_progress": (
                goal_summary["average_progress"] or 0
            ),
            "reviews": reviews,
            "review_counts": review_counts,
            "average_rating": average_rating or 0,
            "performance_status_choices": (
                PerformanceReview.Status.choices
            ),
            "search_query": search_query,
            "status_filter": status_filter,
            "can_manage_hr": can_manage_hr(membership),
        },
    )


@login_required
def recruitment_dashboard(request):
    membership = get_active_membership(request.user)

    if not has_hr_access(membership):
        return redirect("hr:home")

    company = membership.company
    search_query = request.GET.get("q", "").strip()
    stage_filter = request.GET.get("stage", "").strip()
    requisition_filter = request.GET.get(
        "requisition",
        "",
    ).strip()

    requisitions = (
        JobRequisition.objects.filter(
            company=company,
        )
        .select_related(
            "department",
            "position",
            "hiring_manager",
            "recruiter",
        )
        .order_by(
            "-created_at",
            "requisition_number",
        )
    )

    applications = (
        JobApplication.objects.filter(
            company=company,
        )
        .select_related(
            "candidate",
            "requisition",
            "requisition__department",
            "requisition__position",
            "assigned_recruiter",
        )
        .order_by(
            "-applied_at",
            "-created_at",
        )
    )

    if search_query:
        applications = applications.filter(
            Q(candidate__first_name__icontains=search_query)
            | Q(candidate__last_name__icontains=search_query)
            | Q(candidate__email__icontains=search_query)
            | Q(
                requisition__requisition_number__icontains=(
                    search_query
                )
            )
            | Q(requisition__title__icontains=search_query)
        )

    valid_stages = {
        value
        for value, _label in JobApplication.Stage.choices
    }

    if stage_filter in valid_stages:
        applications = applications.filter(
            stage=stage_filter,
        )
    else:
        stage_filter = ""

    if requisition_filter:
        applications = applications.filter(
            requisition_id=requisition_filter,
        )

    open_requisitions = requisitions.filter(
        status=JobRequisition.Status.OPEN,
    )

    active_applications = applications.filter(
        status=JobApplication.Status.ACTIVE,
    )

    pipeline_counts = {
        "applied": applications.filter(
            stage=JobApplication.Stage.APPLIED,
        ).count(),
        "screening": applications.filter(
            stage=JobApplication.Stage.SCREENING,
        ).count(),
        "phone_screen": applications.filter(
            stage=JobApplication.Stage.PHONE_SCREEN,
        ).count(),
        "interview": applications.filter(
            stage=JobApplication.Stage.INTERVIEW,
        ).count(),
        "assessment": applications.filter(
            stage=JobApplication.Stage.ASSESSMENT,
        ).count(),
        "offer": applications.filter(
            stage=JobApplication.Stage.OFFER,
        ).count(),
        "hired": applications.filter(
            stage=JobApplication.Stage.HIRED,
        ).count(),
        "rejected": applications.filter(
            stage=JobApplication.Stage.REJECTED,
        ).count(),
        "withdrawn": applications.filter(
            stage=JobApplication.Stage.WITHDRAWN,
        ).count(),
    }

    total_headcount = sum(
        requisition.headcount
        for requisition in open_requisitions
    )
    filled_headcount = sum(
        requisition.filled_headcount
        for requisition in open_requisitions
    )

    fill_rate = 0

    if total_headcount:
        fill_rate = (
            filled_headcount
            / total_headcount
            * 100
        )

    return render(
        request,
        "hr/recruitment_dashboard.html",
        {
            "current_membership": membership,
            "requisitions": requisitions,
            "open_requisitions": open_requisitions[:8],
            "open_requisition_count": (
                open_requisitions.count()
            ),
            "candidate_count": Candidate.objects.filter(
                company=company,
            ).count(),
            "application_count": applications.count(),
            "active_application_count": (
                active_applications.count()
            ),
            "pipeline_counts": pipeline_counts,
            "total_headcount": total_headcount,
            "filled_headcount": filled_headcount,
            "fill_rate": fill_rate,
            "recent_applications": applications[:10],
            "application_stage_choices": (
                JobApplication.Stage.choices
            ),
            "search_query": search_query,
            "stage_filter": stage_filter,
            "requisition_filter": requisition_filter,
            "can_manage_hr": can_manage_hr(membership),
        },
    )


@login_required
def job_requisition_list(request):
    membership = get_active_membership(request.user)

    if not has_hr_access(membership):
        return redirect("hr:home")

    company = membership.company
    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    department_filter = request.GET.get(
        "department",
        "",
    ).strip()

    requisitions = (
        JobRequisition.objects.filter(
            company=company,
        )
        .select_related(
            "department",
            "department__branch",
            "position",
            "hiring_manager",
            "recruiter",
        )
        .annotate(
            application_count=Count(
                "applications",
                distinct=True,
            )
        )
        .order_by(
            "-created_at",
            "requisition_number",
        )
    )

    if search_query:
        requisitions = requisitions.filter(
            Q(requisition_number__icontains=search_query)
            | Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(department__name__icontains=search_query)
            | Q(position__title__icontains=search_query)
        )

    valid_statuses = {
        value
        for value, _label in JobRequisition.Status.choices
    }

    if status_filter in valid_statuses:
        requisitions = requisitions.filter(
            status=status_filter,
        )
    else:
        status_filter = ""

    if department_filter:
        requisitions = requisitions.filter(
            department_id=department_filter,
        )

    departments = (
        Department.objects.filter(
            branch__company=company,
            is_active=True,
        )
        .order_by("name")
    )

    return render(
        request,
        "hr/job_requisition_list.html",
        {
            "current_membership": membership,
            "requisitions": requisitions,
            "departments": departments,
            "status_choices": JobRequisition.Status.choices,
            "search_query": search_query,
            "status_filter": status_filter,
            "department_filter": department_filter,
            "can_manage_hr": can_manage_hr(membership),
        },
    )


@login_required
def job_requisition_create(request):
    membership = get_active_membership(request.user)

    if not can_manage_hr(membership):
        return hr_management_forbidden()

    company = membership.company

    if request.method == "POST":
        form = JobRequisitionForm(
            request.POST,
            company=company,
        )

        if form.is_valid():
            requisition = form.save(commit=False)
            requisition.company = company
            requisition.created_by = request.user
            requisition.status = JobRequisition.Status.DRAFT
            requisition.save()

            messages.success(
                request,
                "İşe alım talebi taslak olarak oluşturuldu.",
            )

            return redirect(
                "hr:job_requisition_detail",
                requisition_id=requisition.id,
            )
    else:
        form = JobRequisitionForm(
            company=company,
        )

    return render(
        request,
        "hr/job_requisition_form.html",
        {
            "current_membership": membership,
            "form": form,
            "page_title": "Yeni İşe Alım Talebi",
            "page_description": (
                "Pozisyon, kontenjan ve işe alım sorumlularını "
                "tanımlayarak yeni bir talep oluşturun."
            ),
            "submit_text": "Talebi Oluştur",
            "cancel_url": reverse(
                "hr:job_requisition_list",
            ),
        },
    )


@login_required
def job_requisition_detail(
    request,
    requisition_id,
):
    membership = get_active_membership(request.user)

    if not has_hr_access(membership):
        return redirect("hr:home")

    requisition = get_object_or_404(
        JobRequisition.objects.select_related(
            "company",
            "department",
            "department__branch",
            "position",
            "hiring_manager",
            "recruiter",
            "created_by",
        ).prefetch_related(
            "applications",
            "applications__candidate",
        ),
        id=requisition_id,
        company=membership.company,
    )

    applications = (
        requisition.applications
        .select_related(
            "candidate",
            "assigned_recruiter",
        )
        .order_by(
            "-applied_at",
        )
    )

    return render(
        request,
        "hr/job_requisition_detail.html",
        {
            "current_membership": membership,
            "requisition": requisition,
            "applications": applications,
            "can_manage_hr": can_manage_hr(membership),
        },
    )


@login_required
def job_requisition_open(
    request,
    requisition_id,
):
    membership = get_active_membership(request.user)

    if not can_manage_hr(membership):
        return hr_management_forbidden()

    requisition = get_object_or_404(
        JobRequisition,
        id=requisition_id,
        company=membership.company,
    )

    if request.method != "POST":
        return redirect(
            "hr:job_requisition_detail",
            requisition_id=requisition.id,
        )

    try:
        open_job_requisition(
            requisition=requisition,
            changed_by=request.user,
        )
    except ValidationError as error:
        messages.error(
            request,
            " ".join(error.messages),
        )
    else:
        messages.success(
            request,
            "İşe alım talebi yayına alındı.",
        )

    return redirect(
        "hr:job_requisition_detail",
        requisition_id=requisition.id,
    )


@login_required
def candidate_list(request):
    membership = get_active_membership(request.user)

    if not has_hr_access(membership):
        return redirect("hr:home")

    company = membership.company
    search_query = request.GET.get("q", "").strip()
    source_filter = request.GET.get("source", "").strip()

    candidates = (
        Candidate.objects.filter(
            company=company,
        )
        .select_related(
            "created_by",
        )
        .annotate(
            application_count=Count(
                "applications",
                distinct=True,
            )
        )
        .order_by(
            "last_name",
            "first_name",
        )
    )

    if search_query:
        candidates = candidates.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(current_title__icontains=search_query)
            | Q(current_company__icontains=search_query)
        )

    valid_sources = {
        value
        for value, _label in Candidate.Source.choices
    }

    if source_filter in valid_sources:
        candidates = candidates.filter(
            source=source_filter,
        )
    else:
        source_filter = ""

    return render(
        request,
        "hr/candidate_list.html",
        {
            "current_membership": membership,
            "candidates": candidates,
            "source_choices": Candidate.Source.choices,
            "search_query": search_query,
            "source_filter": source_filter,
            "can_manage_hr": can_manage_hr(membership),
        },
    )


@login_required
def candidate_create(request):
    membership = get_active_membership(request.user)

    if not can_manage_hr(membership):
        return hr_management_forbidden()

    company = membership.company

    if request.method == "POST":
        form = CandidateForm(
            request.POST,
            request.FILES,
            company=company,
        )

        if form.is_valid():
            candidate = form.save(commit=False)
            candidate.company = company
            candidate.created_by = request.user
            candidate.consent_at = timezone.now()
            candidate.save()

            messages.success(
                request,
                "Aday kartı başarıyla oluşturuldu.",
            )

            return redirect(
                "hr:candidate_detail",
                candidate_id=candidate.id,
            )
    else:
        form = CandidateForm(
            company=company,
        )

    return render(
        request,
        "hr/candidate_form.html",
        {
            "current_membership": membership,
            "form": form,
            "page_title": "Yeni Aday",
            "page_description": (
                "Adayın iletişim, deneyim ve öz geçmiş "
                "bilgilerini kaydedin."
            ),
            "submit_text": "Adayı Kaydet",
            "cancel_url": reverse(
                "hr:candidate_list",
            ),
        },
    )


@login_required
def candidate_detail(
    request,
    candidate_id,
):
    membership = get_active_membership(request.user)

    if not has_hr_access(membership):
        return redirect("hr:home")

    candidate = get_object_or_404(
        Candidate.objects.select_related(
            "company",
            "created_by",
        ),
        id=candidate_id,
        company=membership.company,
    )

    applications = list(
        JobApplication.objects.filter(
            company=membership.company,
            candidate=candidate,
        )
        .select_related(
            "requisition",
            "requisition__department",
            "requisition__position",
            "assigned_recruiter",
            "ai_assessment",
        )
        .prefetch_related(
            "events",
        )
        .order_by(
            "-applied_at",
        )
    )

    can_manage = can_manage_hr(membership)

    application_ai_rows = (
        build_candidate_application_ai_context(
            applications=applications,
            can_request_analysis=can_manage,
        )
    )

    return render(
        request,
        "hr/candidate_detail.html",
        {
            "current_membership": membership,
            "candidate": candidate,
            "applications": applications,
            "application_ai_rows": application_ai_rows,
            "can_manage_hr": can_manage,
        },
    )


@login_required
@require_POST
def candidate_application_ai_assessment_create(
    request,
    candidate_id,
    application_id,
):
    membership = get_active_membership(request.user)

    if not has_hr_access(membership):
        return redirect("hr:home")

    if not can_manage_hr(membership):
        return hr_management_forbidden()

    candidate = get_object_or_404(
        Candidate,
        id=candidate_id,
        company=membership.company,
    )

    application = get_object_or_404(
        JobApplication.objects.select_related(
            "candidate",
            "requisition",
        ),
        id=application_id,
        candidate=candidate,
        company=membership.company,
    )

    _, created = queue_recruitment_ai_assessment(
        application=application,
        requested_by=request.user,
    )

    if created:
        messages.success(
            request,
            "AI aday değerlendirmesi kuyruğa alındı.",
        )
    else:
        messages.success(
            request,
            "AI aday değerlendirmesi yeniden kuyruğa alındı.",
        )

    return redirect(
        "hr:candidate_detail",
        candidate_id=candidate.id,
    )

