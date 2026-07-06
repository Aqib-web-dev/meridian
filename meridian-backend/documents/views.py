from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets

from tenants.models import Membership, TeamMembership

from .models import Document
from .serializers import DocumentSerializer


class DocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentSerializer

    def get_queryset(self):
        user = self.request.user

        membership = Membership.objects.filter(user=user).select_related("tenant").first()
        if membership is None:
            return Document.objects.none()

        team_ids = TeamMembership.objects.filter(
            membership=membership,
        ).values_list("team_id", flat=True)

        return (
            Document.objects.filter(tenant=membership.tenant)
            .filter(
                Q(visibility=Document.Visibility.COMPANY)
                | Q(visibility=Document.Visibility.TEAM, team_id__in=team_ids)
            )
            .select_related("tenant", "team")
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        membership = Membership.objects.select_related("tenant").get(user=self.request.user)
        serializer.save(tenant=membership.tenant)
