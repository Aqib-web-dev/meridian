from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from tenants.models import Membership


class ParselioTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        membership = Membership.objects.select_related("tenant").filter(user=user).first()
        if membership is None:
            raise AuthenticationFailed("User does not belong to a tenant.")

        token["tenant_id"] = str(membership.tenant_id)
        token["company_role"] = membership.role

        return token