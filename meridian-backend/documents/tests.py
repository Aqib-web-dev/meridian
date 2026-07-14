import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.serializers import MeridianTokenObtainPairSerializer
from documents.models import Document, DocumentChunk
from documents.serializers import DocumentSerializer, MAX_DOCUMENT_SIZE_BYTES
from tenants.models import Membership, Team, TeamMembership, Tenant
from unittest.mock import patch

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


def authenticated_client(user):
    """Return an APIClient carrying a real JWT so MeridianJWTAuthentication runs and sets request.tenant/membership."""
    token = MeridianTokenObtainPairSerializer.get_token(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


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


def test_document_api_rejects_anonymous_users():
    """Anonymous users should get 401 (not authenticated) instead of reaching tenant filtering."""
    client = APIClient()
    client.raise_request_exception = False

    response = client.get(reverse("document-list"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


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

def test_document_detail_rejects_cross_tenant_access():
    """A member of another tenant must get 404, not 403, on a document they don't own."""
    tenant = create_tenant("acme")
    other_tenant = create_tenant("beta")
    team = create_team(tenant)
    document = Document.objects.create(
        tenant=tenant, visibility=Document.Visibility.TEAM, team=team,
        title="Legal Policy", original_filename="legal.pdf", file_key="uploads/legal.pdf",
    )
    user, _membership = create_membership(other_tenant, "outsider")
    client = authenticated_client(user)

    response = client.get(reverse("document-detail", args=[document.id]))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_document_upload_rejects_member_uploading_company_document():
    """A plain member (not owner/admin) must be denied a company-wide upload."""
    tenant = create_tenant()
    user, _membership = create_membership(tenant, "regular")  # default role: MEMBER

    client = authenticated_client(user)

    response = client.post(
        reverse("document-list"),
        document_payload(visibility=Document.Visibility.COMPANY, team=""),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN

@patch("documents.views.generate_presigned_upload")
def test_upload_url_returns_presigned_url_for_valid_request(mock_presign):
    mock_presign.return_value = "https://fake-bucket.s3.amazonaws.com/fake-key?X-Amz-Signature=abc"
    tenant = create_tenant()
    user, _membership = create_membership(tenant, "owner", role=Membership.Role.OWNER)
    client = authenticated_client(user)  # real JWT -> request.tenant/membership get set

    response = client.post(
        reverse("document-upload-url"),
        {
            "title": "Q3 Report", "original_filename": "q3.pdf",
            "content_type": "application/pdf", "file_size": 500_000,
            "visibility": "company", "team": "",
        },
    )

    assert response.status_code == 201
    assert response.data["upload_url"] == mock_presign.return_value
    mock_presign.assert_called_once()
