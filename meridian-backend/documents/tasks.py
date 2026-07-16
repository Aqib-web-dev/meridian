from celery import shared_task

from .models import Document

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def process_document_upload(self, document_id):
    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        return

    if document.status != Document.Status.UPLOADED:
        return  # idempotency guard — see Phase 3d for why this line exists

    document.status = Document.Status.PROCESSING
    document.save(update_fields=["status"])

    try:
        # Stub for today — Day 10 replaces this with real S3 read + extraction.
        document.status = Document.Status.READY
        document.save(update_fields=["status"])
    except Exception as exc:
        document.status = Document.Status.FAILED
        document.save(update_fields=["status"])
        raise self.retry(exc=exc)