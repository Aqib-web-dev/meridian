from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from tenants.models import Membership, TeamMembership


class ParselioJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        user, validated_token = result
        tenant_id = validated_token.get("tenant_id")

        membership = Membership.objects.select_related("tenant").filter(
            user=user,
            tenant_id=tenant_id,
        ).first()

        if membership is None:
            raise AuthenticationFailed("Tenant membership is no longer valid.")

        request.tenant = membership.tenant
        request.membership = membership
        request.company_role = membership.role

        active_team_id = request.headers.get("X-Active-Team-Id")
        request.active_team_id = None
        request.active_team_membership = None

        if active_team_id:
            team_membership = TeamMembership.objects.select_related("team").filter(
                membership=membership,
                team_id=active_team_id,
                team__tenant=membership.tenant,
            ).first()

            if team_membership is None:
                raise AuthenticationFailed("Active team is not available to this user.")

            request.active_team_id = active_team_id
            request.active_team_membership = team_membership

        return user, validated_token