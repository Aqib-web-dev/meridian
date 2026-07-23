import uuid

import boto3
from botocore.config import Config
from django.conf import settings


def build_upload_key(tenant_id, filename):
    """Build a tenant-prefixed, collision-safe S3 key for a new document upload."""
    return f"tenants/{tenant_id}/documents/{uuid.uuid4()}/{filename}"


def generate_presigned_upload(key, content_type):
    """Return a short-lived S3 PUT URL scoped to exactly this key and content type."""
    # Sign against the *regional* endpoint. Buckets outside us-east-1 return a
    # 307 redirect on the global endpoint, and a signed PUT can't follow it
    # (the SigV4 signature is bound to the host it was signed for).
    client = boto3.client(
        "s3",
        region_name=settings.AWS_S3_REGION_NAME,
        endpoint_url=f"https://s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com",
        config=Config(signature_version="s3v4"),
    )
    return client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.AWS_QUERYSTRING_EXPIRE,
    )