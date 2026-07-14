# Meridian Backend

Django REST Framework API backend for Meridian, a multi-tenant document-intelligence SaaS.

## Multi-tenancy approach and why

Meridian uses a **shared database, tenant-discriminator-column** approach:
every tenant-owned table carries a `tenant` foreign key (via the abstract
`TenantScopedModel` base), rather than giving each customer a separate
schema or database.

**Why this, not schema-per-tenant or database-per-tenant:** at this stage
one shared schema means one set of migrations, one connection pool, and
trivial cross-tenant analytics -- all real operational cost savings when
the product has not yet needed per-tenant physical isolation. The
tradeoff is discipline: every query touching a tenant-owned model must
filter by tenant, every write must force it, with no exceptions.

**How isolation is actually enforced, end to end:**

1. **Auth resolves tenant identity.** `MeridianJWTAuthentication` reads
   the JWT's `tenant_id` claim, re-verifies a live `Membership` still
   exists for that user+tenant, and attaches `request.tenant` /
   `request.membership` / `request.company_role` before any view code runs.
2. **Views scope every query.** `DocumentViewSet.get_queryset()` filters
   to `tenant=request.tenant` plus team-visibility rules; `perform_create()`
   forces `tenant=request.tenant` on write. Clients never supply their own
   tenant.
3. **Permissions re-check at the object level.** `CanAccessDocument`
   re-verifies `obj.tenant_id == request.tenant.id` even though the
   queryset already filtered by tenant, so isolation holds even if a
   future code path fetches an object a different way.
4. **The database enforces what code might forget.** A `CheckConstraint`
   on `Document` makes an invalid visibility/team combination impossible
   to save regardless of which code path -- API, admin, script, migration
   -- writes the row.

Tenant isolation is deliberately enforced more than once, in different
layers, because each layer protects against a different failure mode:
application code protects the call sites it covers; database constraints
protect every call site, permanently.

## Running locally

```bash
python manage.py runserver          # dev server (uses meridian.settings.dev)
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser

pytest                              # run all tests
pytest documents                    # one app
pytest documents/tests.py::TestName::test_case   # single test
```
