import plistlib
from typing import List, Optional

import pyexiv2
import xattr
from loguru import logger


class MetadataService:
    """
    Handles both EXIF and macOS metadata simultaneously.
    Keeps both metadata types in sync for maximum compatibility.
    """

    FINDER_COMMENT_ATTR = "com.apple.metadata:kMDItemFinderComment"
    FINDER_TAGS_ATTR = "com.apple.metadata:_kMDItemUserTags"
    XMP_SUBJECT_ATTR = "Xmp.dc.subject"

    def __init__(self):
        """Initialize both EXIF and macOS metadata capabilities"""
        self._verify_macos()

    def _verify_macos(self):
        """Verify if running on macOS"""
        import platform

        self.is_macos = platform.system().lower() == "darwin"
        if not self.is_macos:
            logger.warning(
                "Not running on macOS. Only EXIF metadata will be maintained."
            )
        else:
            logger.info(
                "Running on macOS. Both EXIF and macOS metadata will be maintained."
            )

    def set_description(self, file_path: str, description: str) -> None:
        """Set description in both EXIF and macOS metadata"""
        try:
            # Set EXIF description
            with pyexiv2.Image(file_path) as img:
                img.modify_exif(
                    {
                        "Exif.Image.ImageDescription": description,
                        "Exif.Photo.UserComment": description,  # For better compatibility
                    }
                )

            # Set macOS Finder comment if on macOS
            if self.is_macos:
                self._set_macos_description(file_path, description)

            logger.info(f"Successfully set description for {file_path}")

        except Exception as e:
            logger.error(f"Error setting description: {str(e)}")
            raise

    def get_description(self, file_path: str) -> Optional[str]:
        """
        Get description from metadata.
        Prefers macOS metadata if available, falls back to EXIF.
        """
        try:
            description = None

            # Try macOS metadata first if available
            if self.is_macos:
                description = self._get_macos_description(file_path)

            # Fall back to EXIF if no macOS description
            if description is None:
                with pyexiv2.Image(file_path) as img:
                    exif_data = img.read_exif()
                    description = exif_data.get(
                        "Exif.Image.ImageDescription"
                    ) or exif_data.get("Exif.Photo.UserComment")
            return description

        except Exception as e:
            logger.error(f"Error reading description: {str(e)}")
            return None

    def set_tags(self, file_path: str, tags: List[str]) -> None:
        """Set tags in both EXIF and macOS metadata"""
        try:
            # Set EXIF tags
            with pyexiv2.Image(file_path) as img:
                # Store tags as XMP subject for better compatibility
                xmp_data = {self.XMP_SUBJECT_ATTR: tags} if tags else {}
                img.modify_xmp(xmp_data)

            # Set macOS tags if on macOS
            if self.is_macos:
                self._set_macos_tags(file_path, tags)

            logger.info(f"Successfully set tags for {file_path}")

        except Exception as e:
            logger.error(f"Error setting tags: {str(e)}")
            raise

    def get_tags(self, file_path: str) -> List[str]:
        """
        Get tags from metadata.
        Prefers macOS tags if available, falls back to EXIF.
        """
        try:
            tags = []

            # Try macOS tags first if available
            if self.is_macos:
                tags = self._get_macos_tags(file_path)

            # Fall back to EXIF if no macOS tags
            if not tags:
                with pyexiv2.Image(file_path) as img:
                    xmp_data = img.read_xmp()
                    if self.XMP_SUBJECT_ATTR in xmp_data:
                        # XMP subject can be a list or a single string
                        subject = xmp_data[self.XMP_SUBJECT_ATTR]
                        if isinstance(subject, list):
                            tags = subject
                        else:
                            tags = [subject]

            return tags

        except Exception as e:
            logger.error(f"Error reading hybrid tags: {str(e)}")
            return []

    # MacOS Implementation
    def _set_macos_description(self, file_path: str, description: str) -> None:
        """Set description as Finder comment"""
        try:
            comment_bytes = description.encode("utf-8")
            xattr.setxattr(file_path, self.FINDER_COMMENT_ATTR, comment_bytes)
        except Exception as e:
            logger.error(f"Error setting Finder comment: {str(e)}")
            raise

    def _get_macos_description(self, file_path: str) -> Optional[str]:
        """Get description from Finder comment"""
        try:
            comment_bytes = xattr.getxattr(file_path, self.FINDER_COMMENT_ATTR)
            return comment_bytes.decode("utf-8")
        except (OSError, KeyError):
            return None

    def _set_macos_tags(self, file_path: str, tags: List[str]) -> None:
        """Set Finder tags"""
        try:
            tag_data = [f"{tag}\n" for tag in tags]
            plist_data = plistlib.dumps(tag_data)
            xattr.setxattr(file_path, self.FINDER_TAGS_ATTR, plist_data)
        except Exception as e:
            logger.error(f"Error setting Finder tags: {str(e)}")
            raise

    def _get_macos_tags(self, file_path: str) -> List[str]:
        """Get Finder tags"""
        try:
            tag_data = xattr.getxattr(file_path, self.FINDER_TAGS_ATTR)
            if tag_data:
                tag_list = plistlib.loads(tag_data)
                return [tag.strip() for tag in tag_list if tag.strip()]
            return []
        except (OSError, KeyError):
            return []
        except Exception as e:
            logger.error(f"Error reading Finder tags: {str(e)}")
            return []
