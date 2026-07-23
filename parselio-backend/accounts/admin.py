from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from tenants.models import Membership

from .models import User


class MembershipInline(admin.TabularInline):
	model = Membership
	extra = 1
	autocomplete_fields = ("tenant",)
	fields = ("tenant", "role")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
	inlines = [MembershipInline]
