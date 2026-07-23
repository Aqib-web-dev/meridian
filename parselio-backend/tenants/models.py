import uuid

from django.conf import settings
from django.db import models


class Tenant(models.Model):
    """Company or customer account that owns product data."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    """User-company relationship with a company-level role."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "user"], name="unique_membership_per_tenant_user"),
            models.UniqueConstraint(fields=["user"], name="unique_company_membership_per_user_v1"),
        ]

    def __str__(self):
        return f"{self.user} in {self.tenant} as {self.role}"


class TenantScopedModel(models.Model):
    """Reusable abstract base for rows owned by a company."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Team(TenantScopedModel):
    """Group inside a company that controls access to team-specific work."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=80)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="unique_team_slug_per_tenant"),
        ]

    def __str__(self):
        return self.name


class TeamMembership(models.Model):
    """User-team permission link through the user's company membership."""

    class Role(models.TextChoices):
        VIEWER = "viewer", "Viewer"
        CONTRIBUTOR = "contributor", "Contributor"
        MANAGER = "manager", "Manager"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="team_memberships")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="team_memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["membership", "team"], name="unique_team_membership"),
        ]
