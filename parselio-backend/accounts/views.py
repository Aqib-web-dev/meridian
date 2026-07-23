from django.shortcuts import render

from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import ParselioTokenObtainPairSerializer


class ParselioTokenObtainPairView(TokenObtainPairView):
    serializer_class = ParselioTokenObtainPairSerializer