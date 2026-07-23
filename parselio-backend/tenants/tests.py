import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from tenants.models import Membership, Team, TeamMembership, Tenant
from tenants.serializers import TeamMembershipSerializer, TeamSerializer, TenantSerializer


pytestmark = pytest.mark.django_db


def create_user(username="sara"):
    """Create a user for tests that need membership rows."""
    return get_user_model().objects.create_user(username=username, password="testpass123")


def test_tenant_serializer_outputs_server_owned_fields():
    """TenantSerializer should include backend-created id and timestamps in output."""
    tenant = Tenant.objects.create(name="Acme", slug="acme")

    data = TenantSerializer(tenant).data

    assert data["id"] == str(tenant.id)
    assert data["name"] == "Acme"
    assert data["slug"] == "acme"
    assert "created_at" in data
    assert "updated_at" in data


def test_team_serializer_accepts_input_without_tenant():
    """Team input should not require the frontend to send tenant."""
    serializer = TeamSerializer(data={"name": "Legal", "slug": "legal"})

    assert serializer.is_valid(), serializer.errors
    assert "tenant" not in serializer.validated_data


def test_user_can_only_have_one_company_membership_in_v1():
    """The v1 rule should stop one user from joining two companies."""
    user = create_user()
    acme = Tenant.objects.create(name="Acme", slug="acme")
    beta = Tenant.objects.create(name="Beta", slug="beta")
    Membership.objects.create(tenant=acme, user=user, role=Membership.Role.MEMBER)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Membership.objects.create(tenant=beta, user=user, role=Membership.Role.MEMBER)


def test_team_slug_is_unique_inside_one_tenant_only():
    """Two companies may use the same team slug, but one company may not repeat it."""
    acme = Tenant.objects.create(name="Acme", slug="acme")
    beta = Tenant.objects.create(name="Beta", slug="beta")
    Team.objects.create(tenant=acme, name="Legal", slug="legal")
    Team.objects.create(tenant=beta, name="Legal", slug="legal")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Team.objects.create(tenant=acme, name="Legal Copy", slug="legal")


def test_team_membership_is_unique_per_membership_and_team():
    """The same company member should not be added to the same team twice."""
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    team = Team.objects.create(tenant=tenant, name="Legal", slug="legal")
    membership = Membership.objects.create(tenant=tenant, user=create_user(), role=Membership.Role.MEMBER)
    TeamMembership.objects.create(membership=membership, team=team, role=TeamMembership.Role.VIEWER)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            TeamMembership.objects.create(membership=membership, team=team, role=TeamMembership.Role.CONTRIBUTOR)


def test_team_membership_serializer_accepts_permission_role_input():
    """TeamMembershipSerializer should validate team role input."""
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    team = Team.objects.create(tenant=tenant, name="Legal", slug="legal")
    membership = Membership.objects.create(tenant=tenant, user=create_user(), role=Membership.Role.MEMBER)

    serializer = TeamMembershipSerializer(
        data={
            "membership": str(membership.id),
            "team": str(team.id),
            "role": TeamMembership.Role.CONTRIBUTOR,
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["role"] == TeamMembership.Role.CONTRIBUTOR
