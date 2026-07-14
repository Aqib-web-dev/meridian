from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response

from documents.services import build_upload_key, generate_presigned_upload
from .permissions import (
    CanAccessDocument,
    CanUploadCompanyDocument,
    CanUploadTeamDocument,
    IsTenantMember,
)
from rest_framework import viewsets

from tenants.models import Membership, TeamMembership

from .models import Document
from .serializers import DocumentSerializer


class DocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsTenantMember]
    serializer_class = DocumentSerializer

    def get_permissions(self):
        if self.action == "create":
            return [
                IsAuthenticated(),
                IsTenantMember(),
                CanUploadCompanyDocument(),
                CanUploadTeamDocument(),
            ]
        if self.action in ("retrieve", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsTenantMember(), CanAccessDocument()]
        return super().get_permissions()


    def get_queryset(self):
        team_ids = TeamMembership.objects.filter(
            membership=self.request.membership,
        ).values_list("team_id", flat=True)

        return (
            Document.objects.filter(tenant=self.request.tenant)
            .filter(
                Q(visibility=Document.Visibility.COMPANY)
                | Q(visibility=Document.Visibility.TEAM, team_id__in=team_ids)
            )
            .select_related("tenant", "team")
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)
        
    @action(detail=False, methods=["post"], url_path="upload-url")
    def upload_url(self, request):
        # Same serializer, same validate() — size/type/visibility/role checks unchanged.
        serializer = DocumentSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)   # 400 with field errors if anything fails

        key = build_upload_key(request.tenant.id, serializer.validated_data["original_filename"])
        document = serializer.save(tenant=request.tenant, file_key=key)   # row created up front

        upload_url = generate_presigned_upload(
            key=key,
            content_type=serializer.validated_data["content_type"],
        )
        return Response(
            {"upload_url": upload_url, "document": DocumentSerializer(document).data},
            status=201,
        )
