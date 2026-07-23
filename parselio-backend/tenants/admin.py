from django.contrib import admin

from .models import Membership, Team, TeamMembership, Tenant


class TeamInline(admin.TabularInline):
	model = Team
	extra = 1
	fields = ("name", "slug")


class TeamMembershipInline(admin.TabularInline):
	model = TeamMembership
	extra = 1
	autocomplete_fields = ("membership",)
	fields = ("membership", "role")


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
	list_display = ("name", "slug", "created_at")
	search_fields = ("name", "slug")
	inlines = [TeamInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
	list_display = ("user", "tenant", "role", "created_at")
	list_filter = ("role", "tenant")
	search_fields = ("user__username", "user__email", "tenant__name", "tenant__slug")
	inlines = [TeamMembershipInline]


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
	list_display = ("name", "slug", "tenant", "created_at")
	list_filter = ("tenant",)
	search_fields = ("name", "slug", "tenant__name", "tenant__slug")
	inlines = [TeamMembershipInline]


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
	list_display = ("membership", "team", "role", "created_at")
	list_filter = ("role", "team__tenant")
	search_fields = ("membership__user__username", "team__name", "team__slug")
