"""S3 storage utilities for media files"""

import logging
import os
from typing import Optional
from uuid import uuid4
import mimetypes

import boto3
from botocore.exceptions import ClientError

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class S3Storage:
    """
    S3 storage manager for uploading and managing media files

    Features:
    - Upload files to S3 with automatic content type detection
    - Generate unique filenames to prevent collisions
    - Public URL generation for uploaded files
    - Error handling and logging
    """

    def __init__(self):
        """Initialize S3 client with credentials from settings"""
        self.bucket_name = settings.aws_s3_bucket
        self.region = settings.aws_s3_region

        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=self.region
        )

    def upload_file(
        self,
        file_path: str,
        folder: str = "media",
        public: bool = True
    ) -> Optional[str]:
        """
        Upload a file to S3 and return its URL

        Args:
            file_path: Local path to the file to upload
            folder: S3 folder/prefix (default: "media")
            public: Make file publicly accessible (default: True)

        Returns:
            S3 URL (s3://bucket/key) or None if upload failed

        Example:
            storage = S3Storage()
            url = storage.upload_file("/tmp/photo.jpg", folder="telegram/media")
            # Returns: "s3://aismm-media/telegram/media/abc123.jpg"
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return None

            # Generate unique filename
            file_extension = os.path.splitext(file_path)[1]
            unique_filename = f"{uuid4()}{file_extension}"
            s3_key = f"{folder}/{unique_filename}"

            # Detect content type
            content_type, _ = mimetypes.guess_type(file_path)
            if not content_type:
                content_type = 'application/octet-stream'

            # Upload file
            extra_args = {
                'ContentType': content_type
            }

            if public:
                extra_args['ACL'] = 'public-read'

            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                s3_key,
                ExtraArgs=extra_args
            )

            # Return S3 URL in s3:// format
            s3_url = f"s3://{self.bucket_name}/{s3_key}"
            logger.info(f"Uploaded file to S3: {s3_url}")

            return s3_url

        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error uploading to S3: {e}")
            return None

    def get_public_url(self, s3_url: str) -> Optional[str]:
        """
        Convert s3:// URL to public HTTPS URL

        Args:
            s3_url: S3 URL in format s3://bucket/key

        Returns:
            Public HTTPS URL or None if invalid

        Example:
            url = storage.get_public_url("s3://aismm-media/media/abc123.jpg")
            # Returns: "https://aismm-media.s3.us-east-1.amazonaws.com/media/abc123.jpg"
        """
        try:
            if not s3_url.startswith('s3://'):
                return None

            # Parse s3:// URL
            parts = s3_url.replace('s3://', '').split('/', 1)
            if len(parts) != 2:
                return None

            bucket, key = parts

            # Generate public URL
            if self.region == 'us-east-1':
                public_url = f"https://{bucket}.s3.amazonaws.com/{key}"
            else:
                public_url = f"https://{bucket}.s3.{self.region}.amazonaws.com/{key}"

            return public_url

        except Exception as e:
            logger.error(f"Failed to generate public URL: {e}")
            return None

    def delete_file(self, s3_url: str) -> bool:
        """
        Delete a file from S3

        Args:
            s3_url: S3 URL in format s3://bucket/key

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            if not s3_url.startswith('s3://'):
                return False

            # Parse s3:// URL
            parts = s3_url.replace('s3://', '').split('/', 1)
            if len(parts) != 2:
                return False

            bucket, key = parts

            # Delete object
            self.s3_client.delete_object(Bucket=bucket, Key=key)
            logger.info(f"Deleted file from S3: {s3_url}")

            return True

        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting from S3: {e}")
            return False

    def file_exists(self, s3_url: str) -> bool:
        """
        Check if a file exists in S3

        Args:
            s3_url: S3 URL in format s3://bucket/key

        Returns:
            True if file exists, False otherwise
        """
        try:
            if not s3_url.startswith('s3://'):
                return False

            # Parse s3:// URL
            parts = s3_url.replace('s3://', '').split('/', 1)
            if len(parts) != 2:
                return False

            bucket, key = parts

            # Check if object exists
            self.s3_client.head_object(Bucket=bucket, Key=key)
            return True

        except ClientError:
            return False
        except Exception as e:
            logger.error(f"Error checking file existence: {e}")
            return False


# Global instance
_s3_storage = None


def get_s3_storage() -> S3Storage:
    """
    Get global S3Storage instance (singleton pattern)

    Returns:
        S3Storage instance
    """
    global _s3_storage
    if _s3_storage is None:
        _s3_storage = S3Storage()
    return _s3_storage
