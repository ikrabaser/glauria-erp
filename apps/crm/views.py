import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from .forms import CustomerForm, OpportunityForm
from .models import Customer, Opportunity


def get_active_membership(user):
    return (
        user.organization_memberships
        .filter(is_active=True)
        .order_by("-is_primary", "created_at")
        .first()
    )


@login_required
def home(request):
    membership = get_active_membership(request.user)

    query = request.GET.get("q", "").strip()
    selected_customer_type = request.GET.get("customer_type", "")
    selected_status = request.GET.get("status", "")

    if membership:
        customers = (
            Customer.objects
            .select_related("company", "created_by")
            .filter(company=membership.company)
        )

        if query:
            customers = customers.filter(
                Q(name__icontains=query)
                | Q(email__icontains=query)
                | Q(phone__icontains=query)
                | Q(city__icontains=query)
            )

        if selected_customer_type in Customer.CustomerType.values:
            customers = customers.filter(
                customer_type=selected_customer_type
            )

        if selected_status in Customer.Status.values:
            customers = customers.filter(status=selected_status)
    else:
        customers = Customer.objects.none()

    return render(
        request,
        "crm/home.html",
        {
            "customers": customers,
            "current_membership": membership,
            "query": query,
            "selected_customer_type": selected_customer_type,
            "selected_status": selected_status,
            "customer_type_choices": Customer.CustomerType.choices,
            "status_choices": Customer.Status.choices,
        },
    )


@login_required
def customer_create(request):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("crm:home")

    if request.method == "POST":
        form = CustomerForm(request.POST)

        if form.is_valid():
            customer = form.save(commit=False)
            customer.company = membership.company
            customer.created_by = request.user
            customer.save()

            return redirect("crm:home")
    else:
        form = CustomerForm(
            initial={"status": Customer.Status.LEAD}
        )

    return render(
        request,
        "crm/customer_form.html",
        {
            "form": form,
            "current_membership": membership,
        },
    )
@login_required
def customer_detail(request, customer_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("crm:home")

    customer = get_object_or_404(
        Customer.objects.select_related("company", "created_by"),
        id=customer_id,
        company=membership.company,
    )

    return render(
        request,
        "crm/customer_detail.html",
        {
            "customer": customer,
            "current_membership": membership,
        },
    )
@login_required
def customer_update(request, customer_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("crm:home")

    customer = get_object_or_404(
        Customer.objects.select_related("company", "created_by"),
        id=customer_id,
        company=membership.company,
    )

    if request.method == "POST":
        form = CustomerForm(
            request.POST,
            instance=customer,
        )

        if form.is_valid():
            form.save()

            return redirect(
                "crm:customer_detail",
                customer_id=customer.id,
            )
    else:
        form = CustomerForm(instance=customer)

    return render(
        request,
        "crm/customer_form.html",
        {
            "form": form,
            "customer": customer,
            "current_membership": membership,
            "is_edit": True,
        },
    )
@login_required
def opportunities_home(request):
    membership = get_active_membership(request.user)

    if membership:
        opportunities = (
            Opportunity.objects
            .select_related("customer", "owner")
            .filter(company=membership.company)
        )
    else:
        opportunities = Opportunity.objects.none()

    pipeline = []

    for stage_value, stage_label in Opportunity.Stage.choices:
        stage_opportunities = opportunities.filter(stage=stage_value)

        pipeline.append(
            {
                "key": stage_value,
                "label": stage_label,
                "opportunities": stage_opportunities,
                "count": stage_opportunities.count(),
            }
        )

    return render(
        request,
        "crm/opportunities_home.html",
        {
            "pipeline": pipeline,
            "current_membership": membership,
        },
    )


@login_required
def opportunity_create(request):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("crm:home")

    form = OpportunityForm(request.POST or None)
    form.fields["customer"].queryset = Customer.objects.filter(
        company=membership.company
    ).order_by("name")

    if request.method == "POST" and form.is_valid():
        opportunity = form.save(commit=False)
        opportunity.company = membership.company
        opportunity.owner = request.user
        opportunity.save()

        return redirect("crm:opportunities_home")

    return render(
        request,
        "crm/opportunity_form.html",
        {
            "form": form,
            "current_membership": membership,
        },
    )
@login_required
@require_POST
def opportunity_update_stage(request, opportunity_id):
    membership = get_active_membership(request.user)

    if not membership:
        return JsonResponse(
            {"error": "Aktif şirket üyeliği bulunamadı."},
            status=403,
        )

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Geçersiz istek verisi."},
            status=400,
        )

    stage = payload.get("stage")

    valid_stages = set(Opportunity.Stage.values)

    if stage not in valid_stages:
        return JsonResponse(
            {"error": "Geçersiz fırsat aşaması."},
            status=400,
        )

    opportunity = get_object_or_404(
        Opportunity,
        id=opportunity_id,
        company=membership.company,
    )

    opportunity.stage = stage
    opportunity.save(
        update_fields=["stage", "updated_at"]
    )

    return JsonResponse(
        {
            "id": str(opportunity.id),
            "stage": opportunity.stage,
            "stage_label": opportunity.get_stage_display(),
        }
    )