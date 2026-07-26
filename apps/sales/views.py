from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.http import HttpResponseBadRequest


from apps.crm.models import Customer, Opportunity

from .forms import SalesQuoteForm, SalesQuoteLineForm
from .models import SalesQuote


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

    if membership:
        quotes = (
            SalesQuote.objects
            .select_related("customer", "opportunity", "owner")
            .filter(company=membership.company)
        )
    else:
        quotes = SalesQuote.objects.none()

    return render(
        request,
        "sales/home.html",
        {
            "quotes": quotes,
            "current_membership": membership,
        },
    )


@login_required
def quote_create(request, opportunity_id=None):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("sales:home")

    initial = {}

    if opportunity_id:
        opportunity = get_object_or_404(
            Opportunity,
            id=opportunity_id,
            company=membership.company,
        )

        initial = {
            "customer": opportunity.customer,
            "opportunity": opportunity,
            "title": opportunity.title,
        }

    form = SalesQuoteForm(
        request.POST or None,
        initial=initial,
    )

    form.fields["customer"].queryset = Customer.objects.filter(
        company=membership.company
    ).order_by("name")

    form.fields["opportunity"].queryset = Opportunity.objects.filter(
        company=membership.company
    ).order_by("-updated_at")

    if request.method == "POST" and form.is_valid():
        quote = form.save(commit=False)
        quote.company = membership.company
        quote.owner = request.user
        quote.save()

        return redirect(
            "sales:quote_detail",
            quote_id=quote.id,
        )

    return render(
        request,
        "sales/quote_form.html",
        {
            "form": form,
            "current_membership": membership,
            "opportunity": initial.get("opportunity"),
        },
    )


@login_required
def quote_detail(request, quote_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("sales:home")

    quote = get_object_or_404(
        SalesQuote.objects.select_related(
            "customer",
            "opportunity",
            "owner",
        ).prefetch_related("lines"),
        id=quote_id,
        company=membership.company,
    )

    return render(
        request,
        "sales/quote_detail.html",
        {
            "quote": quote,
            "line_form": SalesQuoteLineForm(),
            "current_membership": membership,
        },
    )
@login_required
@require_POST
def quote_line_create(request, quote_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("sales:home")

    quote = get_object_or_404(
        SalesQuote,
        id=quote_id,
        company=membership.company,
    )

    form = SalesQuoteLineForm(request.POST)

    if form.is_valid():
        line = form.save(commit=False)
        line.quote = quote
        line.line_order = quote.lines.count() + 1
        line.save()

        quote.recalculate_totals()

    return redirect(
        "sales:quote_detail",
        quote_id=quote.id,
    )
@login_required
@require_POST
def quote_status_update(request, quote_id, status):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("sales:home")

    allowed_statuses = {
        SalesQuote.Status.SENT,
        SalesQuote.Status.ACCEPTED,
    }

    if status not in allowed_statuses:
        return HttpResponseBadRequest("Geçersiz teklif durumu.")

    quote = get_object_or_404(
        SalesQuote.objects.select_related("opportunity"),
        id=quote_id,
        company=membership.company,
    )

    quote.status = status
    quote.save(update_fields=["status", "updated_at"])

    if quote.opportunity:
        if status == SalesQuote.Status.SENT:
            quote.opportunity.quote_status = Opportunity.QuoteStatus.SENT
            quote.opportunity.save(update_fields=["quote_status", "updated_at"])

        elif status == SalesQuote.Status.ACCEPTED:
            quote.opportunity.quote_status = Opportunity.QuoteStatus.ACCEPTED
            quote.opportunity.stage = Opportunity.Stage.WON
            quote.opportunity.save(
                update_fields=["quote_status", "stage", "updated_at"]
            )

    return redirect("sales:quote_detail", quote_id=quote.id)