from django.shortcuts import render

from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import MeridianTokenObtainPairSerializer


class MeridianTokenObtainPairView(TokenObtainPairView):
    serializer_class = MeridianTokenObtainPairSerializer