import os
import uuid
import hmac
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger("evently.storage")

ALLOWED_IMAGE_TYPES: Dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def validate_image_bytes(content: bytes) -> bool:
    """
    Validates genuine magic bytes for JPEG, PNG, or WEBP.
    """
    if len(content) < 12:
        return False
    # JPEG magic bytes: FF D8 FF
    if content.startswith(b"\xff\xd8\xff"):
        return True
    # PNG magic bytes: 89 50 4E 47 0D 0A 1A 0A
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    # WEBP magic bytes: RIFF....WEBP
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return True
    return False


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _get_signature_key(key: str, date_stamp: str, region_name: str, service_name: str) -> bytes:
    k_date = _sign(("AWS4" + key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region_name)
    k_service = _sign(k_region, service_name)
    k_signing = _sign(k_service, "aws4_request")
    return k_signing


class StorageService:
    def __init__(self):
        self._local_dir: Optional[Path] = None

    def get_local_storage_dir(self) -> Path:
        """
        Resolves persistent local storage directory.
        Priority:
        1. settings.STORAGE_LOCAL_DIR
        2. RAILWAY_VOLUME_MOUNT_PATH (if Railway persistent volume is attached)
        3. <backend_root>/../uploads (default repository root directory)
        """
        if self._local_dir is not None:
            return self._local_dir

        env_dir = (
            settings.STORAGE_LOCAL_DIR
            or os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
        )

        if env_dir:
            p = Path(env_dir).resolve()
        elif Path("/data").exists() and Path("/data").is_dir() and os.access("/data", os.W_OK):
            # Standard persistent volume mounted at /data
            p = Path("/data/uploads").resolve()
        else:
            # Resolve to root uploads directory: backend/app/services -> repo_root/uploads
            p = Path(__file__).resolve().parent.parent.parent.parent / "uploads"

        p.mkdir(parents=True, exist_ok=True)
        self._local_dir = p
        return self._local_dir

    def get_storage_diagnostics(self) -> Dict[str, Any]:
        """
        Returns safe storage diagnostic metadata for observability.
        NEVER leaks tokens, credentials, or secret keys.
        """
        is_s3 = settings.is_s3_storage_configured and settings.STORAGE_BACKEND != "local"
        local_dir = self.get_local_storage_dir()

        # Check if local storage is backed by a mounted volume
        is_volume_env = bool(settings.STORAGE_LOCAL_DIR or os.getenv("RAILWAY_VOLUME_MOUNT_PATH"))
        is_mount_point = False
        try:
            is_mount_point = os.path.ismount(str(local_dir)) or os.path.ismount(str(local_dir.parent))
        except Exception:
            pass

        is_volume = is_volume_env or is_mount_point or str(local_dir).startswith("/data")

        if is_s3:
            backend_type = "s3"
            persistent = True
        elif is_volume:
            backend_type = "railway_volume"
            persistent = True
        else:
            backend_type = "ephemeral_container"
            persistent = False

        return {
            "backend": backend_type,
            "persistent": persistent,
            "active_dir": str(local_dir),
            "s3_configured": is_s3,
            "s3_bucket": settings.effective_storage_bucket if is_s3 else None,
            "volume_detected": is_volume,
        }

    def validate_image(self, content: bytes, content_type: str) -> str:
        """
        Validates content-type, file size limit (5MB), and genuine magic bytes.
        Returns the appropriate file extension (.jpg, .png, .webp).
        Raises HTTPException 400 if validation fails.
        """
        content_type_clean = (content_type or "").lower().split(";")[0].strip()
        if content_type_clean not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported image type: '{content_type_clean}'. Allowed: JPEG, PNG, WEBP."
            )

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File exceeds maximum allowed size of 5 MB."
            )

        if not validate_image_bytes(content):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image format: file signature does not match genuine image."
            )

        return ALLOWED_IMAGE_TYPES[content_type_clean]

    async def save_image(
        self,
        content: bytes,
        content_type: str,
        folder: str = "covers"
    ) -> str:
        """
        Validates and permanently stores an uploaded image.
        Returns the persistent public URL (S3 HTTPS URL or local /uploads/... path).
        """
        ext = self.validate_image(content, content_type)
        content_type_clean = (content_type or "").lower().split(";")[0].strip()
        filename = f"{uuid.uuid4().hex}{ext}"

        # If S3 is configured, upload to S3-compatible persistent storage
        if settings.is_s3_storage_configured and settings.STORAGE_BACKEND != "local":
            try:
                s3_url = await self._upload_to_s3(
                    content=content,
                    content_type=content_type_clean,
                    key=f"{folder}/{filename}"
                )
                logger.info(f"Uploaded media to S3: {s3_url}")
                return s3_url
            except Exception as e:
                logger.error(f"S3 upload failed, falling back to local persistent storage: {e}")
                # Fall back to local storage if S3 fails
                return self._save_to_local(content, folder, filename)

        # Fall back to local persistent storage (Railway volume or disk)
        return self._save_to_local(content, folder, filename)

    def _save_to_local(self, content: bytes, folder: str, filename: str) -> str:
        base_dir = self.get_local_storage_dir()
        target_dir = base_dir / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename

        with open(target_path, "wb") as f:
            f.write(content)

        logger.info(f"Saved media to local storage: {target_path}")
        return f"/uploads/{folder}/{filename}"

    async def _upload_to_s3(self, content: bytes, content_type: str, key: str) -> str:
        """
        Uploads an object to S3-compatible storage using boto3 if available,
        or pure asynchronous AWS SigV4 over httpx.
        """
        # Try boto3 first if installed
        try:
            import boto3
            import asyncio
            from botocore.config import Config

            endpoint = settings.effective_storage_endpoint
            bucket = settings.effective_storage_bucket
            access_key = settings.effective_storage_access_key
            secret_key = settings.effective_storage_secret_key
            region = settings.effective_storage_region

            def _boto_put():
                s3_client = boto3.client(
                    "s3",
                    endpoint_url=endpoint,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name=region,
                    config=Config(s3={"addressing_style": "path"})
                )
                s3_client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=content,
                    ContentType=content_type
                )

            await asyncio.to_thread(_boto_put)
            return self._build_s3_url(key)
        except ImportError:
            # Fall back to direct async AWS SigV4 implementation via httpx
            return await self._upload_s3_sigv4(content, content_type, key)

    async def _upload_s3_sigv4(self, content: bytes, content_type: str, key: str) -> str:
        """
        Pure Python asynchronous S3 PUT object using AWS Signature Version 4.
        Works seamlessly with Cloudflare R2, AWS S3, MinIO, Supabase, Yandex Cloud.
        """
        endpoint = settings.effective_storage_endpoint or "https://s3.amazonaws.com"
        bucket = settings.effective_storage_bucket or ""
        access_key = settings.effective_storage_access_key or ""
        secret_key = settings.effective_storage_secret_key or ""
        region = settings.effective_storage_region or "us-east-1"

        parsed_endpoint = urlparse(endpoint)
        scheme = parsed_endpoint.scheme or "https"
        netloc = parsed_endpoint.netloc

        # Standard S3 path-style URL: https://<endpoint_host>/<bucket>/<key>
        canonical_uri = f"/{bucket}/{key}"
        url = f"{scheme}://{netloc}{canonical_uri}"

        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        payload_hash = hashlib.sha256(content).hexdigest()

        headers_to_sign = {
            "content-type": content_type,
            "host": netloc,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }

        canonical_headers = "".join(f"{k}:{v}\n" for k, v in sorted(headers_to_sign.items()))
        signed_headers = ";".join(sorted(headers_to_sign.keys()))

        canonical_request = (
            f"PUT\n"
            f"{canonical_uri}\n"
            f"\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{payload_hash}"
        )

        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{region}/s3/aws4_request"
        string_to_sign = (
            f"{algorithm}\n"
            f"{amz_date}\n"
            f"{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )

        signing_key = _get_signature_key(secret_key, date_stamp, region, "s3")
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        authorization_header = (
            f"{algorithm} "
            f"Credential={access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        request_headers = {
            "Content-Type": content_type,
            "Host": netloc,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
            "Authorization": authorization_header,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.put(url, headers=request_headers, content=content)
            if resp.status_code not in (200, 201, 204):
                raise RuntimeError(
                    f"S3 returned status {resp.status_code}: {resp.text[:200]}"
                )

        return self._build_s3_url(key)

    def _build_s3_url(self, key: str) -> str:
        """
        Builds public URL for uploaded S3 key.
        """
        if settings.effective_storage_public_url:
            return f"{settings.effective_storage_public_url}/{key}"

        endpoint = (settings.effective_storage_endpoint or "https://s3.amazonaws.com").rstrip("/")
        bucket = settings.effective_storage_bucket
        return f"{endpoint}/{bucket}/{key}"


storage_service = StorageService()
