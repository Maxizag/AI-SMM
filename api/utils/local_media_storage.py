"""Local media storage for testing without S3"""

import logging
import os
from typing import Optional
from uuid import uuid4
import shutil

logger = logging.getLogger(__name__)


class LocalMediaStorage:
    """
    Local filesystem storage for media files

    Alternative to S3Storage for local testing.
    Saves files to local media/ directory.
    """

    def __init__(self, base_dir: str = "media"):
        """
        Initialize local storage

        Args:
            base_dir: Base directory for media files (default: "media")
        """
        self.base_dir = base_dir

        # Create base directory if it doesn't exist
        os.makedirs(base_dir, exist_ok=True)

    def upload_file(
        self,
        file_path: str,
        folder: str = "media",
        public: bool = True
    ) -> Optional[str]:
        """
        Copy file to local storage and return its path

        Args:
            file_path: Local path to the file to copy
            folder: Subfolder (e.g., "telegram/channel")
            public: Ignored (for S3 compatibility)

        Returns:
            Local file URL (file:///path/to/file) or None if failed
        """
        try:
            # Check if source file exists
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return None

            # Generate unique filename
            file_extension = os.path.splitext(file_path)[1]
            unique_filename = f"{uuid4()}{file_extension}"

            # Create destination path
            dest_dir = os.path.join(self.base_dir, folder)
            os.makedirs(dest_dir, exist_ok=True)

            dest_path = os.path.join(dest_dir, unique_filename)

            # Copy file
            shutil.copy2(file_path, dest_path)

            # Return file:// URL with absolute path
            abs_path = os.path.abspath(dest_path)
            file_url = f"file:///{abs_path}"

            logger.info(f"Saved media to: {abs_path}")

            return file_url

        except Exception as e:
            logger.error(f"Failed to save file locally: {e}")
            return None

    def get_public_url(self, file_url: str) -> Optional[str]:
        """
        Get absolute path from file:// URL

        Args:
            file_url: File URL in format file:///path

        Returns:
            Absolute file path
        """
        if file_url.startswith('file:///'):
            return file_url.replace('file:///', '/')
        return file_url

    def delete_file(self, file_url: str) -> bool:
        """
        Delete file from local storage

        Args:
            file_url: File URL in format file:///path

        Returns:
            True if deleted successfully
        """
        try:
            file_path = self.get_public_url(file_url)
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
                logger.info(f"Deleted file: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            return False

    def file_exists(self, file_url: str) -> bool:
        """
        Check if file exists in local storage

        Args:
            file_url: File URL in format file:///path

        Returns:
            True if file exists
        """
        try:
            file_path = self.get_public_url(file_url)
            return file_path and os.path.exists(file_path)
        except Exception:
            return False


# Global instance
_local_storage = None


def get_local_storage(base_dir: str = "media") -> LocalMediaStorage:
    """
    Get global LocalMediaStorage instance (singleton pattern)

    Args:
        base_dir: Base directory for media files

    Returns:
        LocalMediaStorage instance
    """
    global _local_storage
    if _local_storage is None:
        _local_storage = LocalMediaStorage(base_dir)
    return _local_storage
