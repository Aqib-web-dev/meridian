from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
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
