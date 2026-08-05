from dataclasses import dataclass

from apps.accounts.models import OrganizationMembership


AI_TOOL_MODULES = (
    OrganizationMembership.Module.CRM,
    OrganizationMembership.Module.FINANCE,
    OrganizationMembership.Module.INVENTORY,
    OrganizationMembership.Module.HR,
)


@dataclass(frozen=True)
class EnterpriseAIAccessContext:
    membership: OrganizationMembership
    allowed_modules: frozenset[str]

    @property
    def company(self):
        return self.membership.company

    @property
    def has_available_tools(self) -> bool:
        return bool(self.allowed_modules)


def get_active_ai_membership(user):
    if not user.is_authenticated:
        return None

    return (
        user.organization_memberships
        .select_related(
            "company",
            "branch",
            "department",
        )
        .filter(is_active=True)
        .order_by(
            "-is_primary",
            "created_at",
        )
        .first()
    )


def resolve_enterprise_ai_access(user):
    membership = get_active_ai_membership(user)

    if membership is None:
        return None

    allowed_modules = frozenset(
        module
        for module in AI_TOOL_MODULES
        if membership.has_module_access(module)
    )

    return EnterpriseAIAccessContext(
        membership=membership,
        allowed_modules=allowed_modules,
    )
