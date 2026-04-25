import io
import os
import logging
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        self.endpoint = os.environ.get("MINIO_ENDPOINT", "minio:9000")
        self.access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
        self.secure = os.environ.get("MINIO_SECURE", "false").lower() == "true"
        
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )

    async def upload_file(self, bucket_name: str, object_name: str, data: bytes, content_type: str = "application/octet-stream"):
        try:
            # Check if bucket exists
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
            
            # Upload data
            self.client.put_object(
                bucket_name,
                object_name,
                io.BytesIO(data),
                length=len(data),
                content_type=content_type
            )
            logger.info(f"Successfully uploaded {object_name} to {bucket_name}")
            return True
        except S3Error as e:
            logger.error(f"Error uploading file to MinIO: {e}")
            return False

    async def download_file(self, bucket_name: str, object_name: str) -> bytes:
        try:
            response = self.client.get_object(bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            logger.error(f"Error downloading file from MinIO: {e}")
            return None

    def get_presigned_url(self, bucket_name: str, object_name: str, expires_in_seconds: int = 3600):
        try:
            return self.client.presigned_get_object(bucket_name, object_name, expires=expires_in_seconds)
        except S3Error as e:
            logger.error(f"Error generating presigned URL: {e}")
            return None

    async def delete_file(self, bucket_name: str, object_name: str) -> bool:
        try:
            self.client.remove_object(bucket_name, object_name)
            logger.info(f"Successfully deleted {object_name} from {bucket_name}")
            return True
        except S3Error as e:
            logger.error(f"Error deleting file from MinIO: {e}")
            return False
