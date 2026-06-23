import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from documents.models import Document, DocumentChunk
from documents.serializers import DocumentSerializer, MAX_DOCUMENT_SIZE_BYTES
from tenants.models import Membership, Team, TeamMembership, Tenant


pytestmark = pytest.mark.django_db


def create_user(username):
    """Create a user for document permission tests."""
    return get_user_model().objects.create_user(username=username, password="testpass123")


def create_tenant(slug="acme"):
    """Create one company for tests."""
    return Tenant.objects.create(name=slug.title(), slug=slug)


def create_team(tenant, slug="legal"):
    """Create one team inside a company."""
    return Team.objects.create(tenant=tenant, name=slug.title(), slug=slug)


def create_membership(tenant, username, role=Membership.Role.MEMBER):
    """Create one user-company membership."""
    user = create_user(username)
    membership = Membership.objects.create(tenant=tenant, user=user, role=role)
    return user, membership


def document_payload(**overrides):
    """Return valid document input and allow tests to change one rule at a time."""
    payload = {
        "visibility": Document.Visibility.TEAM,
        "team": None,
        "title": "Legal Policy",
        "original_filename": "legal-policy.pdf",
        "file_key": "uploads/legal-policy.pdf",
        "file_size": 500000,
        "content_type": "application/pdf",
    }
    payload.update(overrides)
    return payload


def test_database_allows_company_wide_document_without_team():
    """Company-wide documents should be stored with no team."""
    tenant = create_tenant()

    document = Document.objects.create(
        tenant=tenant,
        visibility=Document.Visibility.COMPANY,
        team=None,
        title="Company Handbook",
        original_filename="handbook.pdf",
        file_key="uploads/handbook.pdf",
    )

    assert document.team is None


def test_database_rejects_company_wide_document_with_team():
    """The database should reject company-wide documents that point to a team."""
    tenant = create_tenant()
    team = create_team(tenant)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Document.objects.create(
                tenant=tenant,
                visibility=Document.Visibility.COMPANY,
                team=team,
                title="Wrong Handbook",
                original_filename="wrong.pdf",
                file_key="uploads/wrong.pdf",
            )


def test_database_rejects_duplicate_chunk_index_inside_one_document():
    """One document should not have two chunks with the same chunk_index."""
    tenant = create_tenant()
    team = create_team(tenant)
    document = Document.objects.create(
        tenant=tenant,
        visibility=Document.Visibility.TEAM,
        team=team,
        title="Legal Policy",
        original_filename="legal-policy.pdf",
        file_key="uploads/legal-policy.pdf",
    )
    DocumentChunk.objects.create(tenant=tenant, document=document, chunk_index=0, text="First chunk")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DocumentChunk.objects.create(tenant=tenant, document=document, chunk_index=0, text="Duplicate chunk")


def test_document_serializer_allows_owner_to_upload_team_document():
    """Company owners should be allowed to upload to any team."""
    tenant = create_tenant()
    team = create_team(tenant)
    user, _membership = create_membership(tenant, "owner", Membership.Role.OWNER)

    serializer = DocumentSerializer(
        data=document_payload(team=str(team.id)),
        context={"tenant": tenant, "user": user},
    )

    assert serializer.is_valid(), serializer.errors
    document = serializer.save(tenant=tenant)
    assert document.team == team
    assert not hasattr(document, "file_size")


def test_document_serializer_counts_chunks_in_output():
    """Document output should include calculated chunk_count."""
    tenant = create_tenant()
    team = create_team(tenant)
    document = Document.objects.create(
        tenant=tenant,
        visibility=Document.Visibility.TEAM,
        team=team,
        title="Legal Policy",
        original_filename="legal-policy.pdf",
        file_key="uploads/legal-policy.pdf",
    )
    DocumentChunk.objects.create(tenant=tenant, document=document, chunk_index=0, text="First chunk")
    DocumentChunk.objects.create(tenant=tenant, document=document, chunk_index=1, text="Second chunk")

    data = DocumentSerializer(document).data

    assert data["chunk_count"] == 2
    assert "file_size" not in data
    assert "content_type" not in data


def test_document_serializer_rejects_file_larger_than_limit():
    """Serializer validation should reject upload metadata above the size limit."""
    tenant = create_tenant()
    team = create_team(tenant)
    user, _membership = create_membership(tenant, "owner", Membership.Role.OWNER)

    serializer = DocumentSerializer(
        data=document_payload(team=str(team.id), file_size=MAX_DOCUMENT_SIZE_BYTES + 1),
        context={"tenant": tenant, "user": user},
    )

    assert not serializer.is_valid()
    assert "file_size" in serializer.errors


def test_document_serializer_rejects_unsupported_content_type():
    """Serializer validation should reject file types Meridian does not accept."""
    tenant = create_tenant()
    team = create_team(tenant)
    user, _membership = create_membership(tenant, "owner", Membership.Role.OWNER)

    serializer = DocumentSerializer(
        data=document_payload(team=str(team.id), content_type="image/png"),
        context={"tenant": tenant, "user": user},
    )

    assert not serializer.is_valid()
    assert "content_type" in serializer.errors


def test_document_serializer_rejects_company_document_with_team():
    """Company-wide document input should not include a team."""
    tenant = create_tenant()
    team = create_team(tenant)
    user, _membership = create_membership(tenant, "owner", Membership.Role.OWNER)

    serializer = DocumentSerializer(
        data=document_payload(visibility=Document.Visibility.COMPANY, team=str(team.id)),
        context={"tenant": tenant, "user": user},
    )

    assert not serializer.is_valid()
    assert "team" in serializer.errors


def test_document_serializer_rejects_team_document_without_team():
    """Team-specific document input should include a team."""
    tenant = create_tenant()
    user, _membership = create_membership(tenant, "owner", Membership.Role.OWNER)

    serializer = DocumentSerializer(
        data=document_payload(team=None),
        context={"tenant": tenant, "user": user},
    )

    assert not serializer.is_valid()
    assert "team" in serializer.errors


def test_document_serializer_rejects_team_from_another_tenant():
    """A document upload should not use a team from another company."""
    tenant = create_tenant("acme")
    other_tenant = create_tenant("beta")
    other_team = create_team(other_tenant)
    user, _membership = create_membership(tenant, "owner", Membership.Role.OWNER)

    serializer = DocumentSerializer(
        data=document_payload(team=str(other_team.id)),
        context={"tenant": tenant, "user": user},
    )

    assert not serializer.is_valid()
    assert "team" in serializer.errors


def test_document_serializer_allows_contributor_to_upload_team_document():
    """Team contributors should be allowed to upload documents to their team."""
    tenant = create_tenant()
    team = create_team(tenant)
    user, membership = create_membership(tenant, "contributor")
    TeamMembership.objects.create(membership=membership, team=team, role=TeamMembership.Role.CONTRIBUTOR)

    serializer = DocumentSerializer(
        data=document_payload(team=str(team.id)),
        context={"tenant": tenant, "user": user},
    )

    assert serializer.is_valid(), serializer.errors


def test_document_serializer_rejects_viewer_upload_to_team_document():
    """Team viewers should not be allowed to upload documents."""
    tenant = create_tenant()
    team = create_team(tenant)
    user, membership = create_membership(tenant, "viewer")
    TeamMembership.objects.create(membership=membership, team=team, role=TeamMembership.Role.VIEWER)

    serializer = DocumentSerializer(
        data=document_payload(team=str(team.id)),
        context={"tenant": tenant, "user": user},
    )

    assert not serializer.is_valid()
    assert "non_field_errors" in serializer.errors


def test_document_serializer_allows_admin_to_upload_company_document():
    """Company admins should be allowed to upload company-wide documents."""
    tenant = create_tenant()
    user, _membership = create_membership(tenant, "admin", Membership.Role.ADMIN)

    serializer = DocumentSerializer(
        data=document_payload(visibility=Document.Visibility.COMPANY, team=None),
        context={"tenant": tenant, "user": user},
    )

    assert serializer.is_valid(), serializer.errors
