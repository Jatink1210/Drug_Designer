"""Distributed Object Storage Client (S3/MinIO) with Local Fallback."""

import os
import shutil
import structlog
from typing import Optional
from config import settings

log = structlog.get_logger(__name__)

# Lazy load boto3 to avoid crashing desktop environments if not installed
try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class StorageClient:
    """Handles object persistence to S3/MinIO or local disk."""
    
    def __init__(self):
        self.use_s3 = BOTO3_AVAILABLE and bool(settings.s3_bucket)
        self.s3_client = None
        
        if self.use_s3:
            try:
                self.s3_client = boto3.client(
                    "s3",
                    endpoint_url=settings.s3_endpoint if settings.s3_endpoint else None,
                    aws_access_key_id=settings.s3_access_key,
                    aws_secret_access_key=settings.s3_secret_key,
                )
                log.info("storage_client_s3_enabled", bucket=settings.s3_bucket)
            except Exception as e:
                log.error("storage_client_s3_init_error", error=str(e))
                self.use_s3 = False

    def upload_file(self, local_path: str, remote_key: str) -> str:
        """Uploads a file and returns its public URL or local path reference."""
        if self.use_s3 and self.s3_client:
            try:
                self.s3_client.upload_file(local_path, settings.s3_bucket, remote_key)
                # Generate a public URL based on endpoint or standard AWS template
                if settings.s3_endpoint:
                    url = f"{settings.s3_endpoint}/{settings.s3_bucket}/{remote_key}"
                else:
                    url = f"https://{settings.s3_bucket}.s3.amazonaws.com/{remote_key}"
                log.debug("storage_client_uploaded_s3", key=remote_key, url=url)
                return url
            except Exception as e:
                log.error("storage_client_s3_upload_failed", error=str(e), falling_back="local")

        # Fallback to local storage copy if requested
        target_path = os.path.join(settings.local_store_path, "public", remote_key)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        shutil.copy2(local_path, target_path)
        log.debug("storage_client_uploaded_local", key=remote_key)
        return f"/api/files/{remote_key}"

    def download_file(self, remote_key: str, local_path: str) -> bool:
        """Pulls a file from S3 to a local temp path."""
        if self.use_s3 and self.s3_client:
            try:
                self.s3_client.download_file(settings.s3_bucket, remote_key, local_path)
                return True
            except Exception as e:
                log.error("storage_client_s3_download_failed", error=str(e))
                return False
        
        # Local fallback
        source_path = os.path.join(settings.local_store_path, "public", remote_key)
        if os.path.exists(source_path):
            shutil.copy2(source_path, local_path)
            return True
        return False

# Global Singleton
storage_client = StorageClient()
