from rest_framework.permissions import BasePermission

from tenants.models import Membership, TeamMembership


from .models import Document


class IsTenantMember(BasePermission):
    """Require a verified company membership before any document action runs."""

    def has_permission(self, request, view):
        return getattr(request, "membership", None) is not None
    
class CanAccessDocument(BasePermission):
    """Gate single-document read/write access after get_object() finds a row."""

    def has_object_permission(self, request, view, obj):
        # Rule 1: never cross the tenant boundary — the outermost, non-negotiable ring.
        if obj.tenant_id != request.tenant.id:
            return False

        # Rule 2: company-wide docs are readable by any member of the tenant.
        if obj.visibility == Document.Visibility.COMPANY:
            return True

        # Rule 3: team docs require the requester to be on that specific team.
        return TeamMembership.objects.filter(
            membership=request.membership,
            team_id=obj.team_id,
        ).exists()

class CanUploadCompanyDocument(BasePermission):
    """Only company owners or admins may create company-wide documents."""

    def has_permission(self, request, view):
        if request.data.get("visibility") != Document.Visibility.COMPANY:
            return True  # not a company-wide upload — this gate doesn't apply
        return request.company_role in (Membership.Role.OWNER, Membership.Role.ADMIN)


class CanUploadTeamDocument(BasePermission):
    """Owners upload anywhere; team contributors/managers upload to their own team."""

    def has_permission(self, request, view):
        if request.data.get("visibility") != Document.Visibility.TEAM:
            return True  # not a team upload — this gate doesn't apply

        if request.company_role == Membership.Role.OWNER:
            return True  # owner override — same rule the serializer already enforces

        team_id = request.data.get("team")
        return TeamMembership.objects.filter(
            membership=request.membership,
            team_id=team_id,
            role__in=[TeamMembership.Role.CONTRIBUTOR, TeamMembership.Role.MANAGER],
        ).exists()