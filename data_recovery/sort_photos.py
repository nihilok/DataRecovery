#!/usr/bin/env python3
"""
Photo File Organizer

This script recursively finds photo files, reads their EXIF data,
and organizes them into a logical directory structure: Year/Month/Date-Time_OriginalName.
Photos without EXIF date information are skipped.
"""

import shutil
import re
from pathlib import Path
from typing import Dict, List, Optional
import argparse
import logging
from datetime import datetime

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
except ImportError:
    print("Error: Pillow library not found. Please install with: pip install Pillow")
    exit(1)


class PhotoOrganizer:
    """Organizes photo files based on their EXIF metadata."""

    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.tiff', '.tif', '.png', '.bmp', '.gif', '.webp', '.heic', '.heif', '.raw', '.cr2', '.nef', '.arw', '.dng'}

    def __init__(self, source_dir: str, target_dir: str, dry_run: bool = False):
        self.source_dir = Path(source_dir).resolve()
        self.target_dir = Path(target_dir).resolve()
        self.dry_run = dry_run
        self.stats = {
            'processed': 0,
            'moved': 0,
            'skipped': 0,
            'errors': 0
        }

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Remove or replace invalid characters for filesystem compatibility."""
        # Replace problematic characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Remove leading/trailing dots and spaces
        filename = filename.strip('. ')
        # Limit length
        if len(filename) > 200:
            filename = filename[:200]
        return filename or "Unknown"

    def extract_exif_date(self, file_path: Path) -> tuple[Optional[datetime], bool]:
        """Extract date taken from EXIF data. Returns (date, had_error)."""
        try:
            with Image.open(file_path) as image:
                exif_data = image._getexif()
                if exif_data is None:
                    return None, False
                # Look for date taken tags
                date_tags = ['DateTime', 'DateTimeOriginal', 'DateTimeDigitized']
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    if tag_name in date_tags:
                        try:
                            # Parse the date string (format: "YYYY:MM:DD HH:MM:SS")
                            return datetime.strptime(value, "%Y:%m:%d %H:%M:%S"), False
                        except ValueError:
                            # Try alternative format
                            try:
                                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S"), False
                            except ValueError:
                                continue
                return None, False
        except Exception as e:
            self.logger.warning(f"Error reading EXIF from {file_path}: {e}")
            return None, True

    def generate_target_path(self, file_path: Path, date_taken: datetime) -> Path:
        """Generate the target path based on date taken."""
        year = date_taken.strftime("%Y")
        month = date_taken.strftime("%m-%B")  # "01-January" format

        # Create timestamp for filename
        timestamp = date_taken.strftime("%Y%m%d_%H%M%S")

        # Get original filename without extension
        original_name = file_path.stem
        original_name = self.sanitize_filename(original_name)

        # Build new filename with timestamp
        filename = f"{timestamp}_{original_name}{file_path.suffix}"
        filename = self.sanitize_filename(filename)

        return self.target_dir / year / month / filename

    def find_photo_files(self) -> List[Path]:
        """Recursively find all photo files in source directory."""
        photo_files = []

        for file_path in self.source_dir.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_FORMATS:
                photo_files.append(file_path)

        return photo_files

    def move_file(self, source: Path, target: Path) -> bool:
        """Move file to target location, creating directories as needed."""
        try:
            if self.dry_run:
                # In dry run mode, just log what would happen without creating directories
                self.logger.info(f"DRY RUN: Would move {source} -> {target}")
                return True

            if target.exists():
                # Handle duplicates by adding a number suffix
                counter = 1
                while target.exists():
                    stem = target.stem
                    suffix = target.suffix
                    parent = target.parent
                    target = parent / f"{stem}_{counter}{suffix}"
                    counter += 1

                self.logger.warning(f"Duplicate found, renaming to: {target.name}")

            # Create target directory only when not in dry run mode
            target.parent.mkdir(parents=True, exist_ok=True)

            shutil.move(str(source), str(target))
            self.logger.info(f"Moved: {source.name} -> {target}")
            return True

        except Exception as e:
            self.logger.error(f"Error moving {source} to {target}: {e}")
            return False

    def organize_photos(self) -> Dict[str, int]:
        """Main method to organize all photo files."""
        self.logger.info(f"Starting photo organization...")
        self.logger.info(f"Source: {self.source_dir}")
        self.logger.info(f"Target: {self.target_dir}")
        self.logger.info(f"Dry run: {self.dry_run}")

        photo_files = self.find_photo_files()
        self.logger.info(f"Found {len(photo_files)} photo files")

        for file_path in photo_files:
            self.stats['processed'] += 1
            date_taken, had_error = self.extract_exif_date(file_path)
            if had_error:
                self.logger.info(f"Error processing {file_path.name} - could not extract EXIF date")
                self.stats['errors'] += 1
                continue
            if date_taken is None:
                self.logger.info(f"Skipping {file_path.name} - no EXIF date found")
                self.stats['skipped'] += 1
                continue
            target_path = self.generate_target_path(file_path, date_taken)
            if self.move_file(file_path, target_path):
                self.stats['moved'] += 1
            else:
                self.stats['errors'] += 1
        self.logger.info("Organization complete!")
        self.logger.info(f"Statistics: {self.stats}")
        return self.stats


def main():
    """Command line interface."""
    parser = argparse.ArgumentParser(
        description="Organize photos by EXIF date into Year/Month folders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python sort_photos.py /path/to/photos /path/to/organized
  python sort_photos.py /path/to/photos /path/to/organized --dry-run
        """
    )

    parser.add_argument(
        'source_dir',
        help='Source directory containing photos to organize'
    )

    parser.add_argument(
        'target_dir',
        help='Target directory for organized photos'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually moving files'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate directories
    source_path = Path(args.source_dir)
    if not source_path.exists():
        print(f"Error: Source directory '{source_path}' does not exist")
        return 1

    if not source_path.is_dir():
        print(f"Error: '{source_path}' is not a directory")
        return 1

    # Create organizer and run
    organizer = PhotoOrganizer(
        source_dir=args.source_dir,
        target_dir=args.target_dir,
        dry_run=args.dry_run
    )

    try:
        stats = organizer.organize_photos()

        print("\n" + "="*50)
        print("ORGANIZATION SUMMARY")
        print("="*50)
        print(f"Total files processed: {stats['processed']}")
        print(f"Files moved: {stats['moved']}")
        print(f"Files skipped (no EXIF): {stats['skipped']}")
        print(f"Errors: {stats['errors']}")
        print("="*50)

        return 0

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
