from rest_framework import serializers

from .models import Membership, Team, TeamMembership, Tenant


class TenantSerializer(serializers.ModelSerializer):
    """Convert company/tenant records to and from API JSON."""

    class Meta:
        model = Tenant
        fields = ["id", "name", "slug", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class MembershipSerializer(serializers.ModelSerializer):
    """Convert user-company membership and company role data to API JSON."""

    class Meta:
        model = Membership
        fields = ["id", "tenant", "user", "role", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class TeamSerializer(serializers.ModelSerializer):
    """Convert company team records to and from API JSON."""

    class Meta:
        model = Team
        fields = ["id", "tenant", "name", "slug", "created_at", "updated_at"]
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class TeamMembershipSerializer(serializers.ModelSerializer):
    """Convert user-team permission links and team roles to API JSON."""

    class Meta:
        model = TeamMembership
        fields = ["id", "membership", "team", "role", "created_at"]
        read_only_fields = ["id", "created_at"]
