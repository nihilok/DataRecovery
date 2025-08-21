#!/usr/bin/env python3
"""
Video File Organizer

This script recursively finds video files, reads their metadata using exiftool,
and organizes them into a logical directory structure: Year/Month/Date-Time_OriginalName.
Videos without creation date information are organized by file modification date.
"""

import shutil
import re
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional
import argparse
import logging
from datetime import datetime


class VideoOrganizer:
    """Organizes video files based on their metadata."""

    SUPPORTED_FORMATS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.mpg', '.mpeg', '.m2v', '.asf', '.ts', '.mts', '.m2ts'}

    def __init__(self, source_dir: str, target_dir: str, dry_run: bool = False, use_ffprobe: bool = False):
        self.source_dir = Path(source_dir).resolve()
        self.target_dir = Path(target_dir).resolve()
        self.dry_run = dry_run
        self.use_ffprobe = use_ffprobe
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

        # Check if the selected tool is available
        if self.use_ffprobe:
            if not self._check_ffprobe():
                raise RuntimeError("ffprobe not found. Please install FFmpeg.")
            self.logger.info("Using ffprobe for metadata extraction")
        else:
            if not self._check_exiftool():
                raise RuntimeError("exiftool not found. Please install ExifTool.")
            self.logger.info("Using exiftool for metadata extraction")

    def _check_exiftool(self) -> bool:
        """Check if exiftool is available on the system."""
        try:
            subprocess.run(['exiftool', '-ver'],
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _check_ffprobe(self) -> bool:
        """Check if ffprobe is available on the system."""
        try:
            subprocess.run(['ffprobe', '-version'],
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Remove or replace invalid characters for filesystem compatibility."""
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.strip('. ')
        if len(filename) > 200:
            filename = filename[:200]
        return filename or "Unknown"

    def extract_video_metadata(self, file_path: Path) -> tuple[Optional[datetime], bool]:
        """Extract creation date from video metadata using exiftool or ffprobe. Returns (date, had_error)."""
        if self.use_ffprobe:
            return self._extract_metadata_ffprobe(file_path)
        else:
            return self._extract_metadata_exiftool(file_path)

    def _extract_metadata_exiftool(self, file_path: Path) -> tuple[Optional[datetime], bool]:
        """Extract creation date from video metadata using exiftool."""
        try:
            # Use exiftool to extract metadata
            cmd = [
                'exiftool',
                '-s',  # Short format
                '-CreateDate',
                '-MediaCreateDate',
                '-TrackCreateDate',
                '-CreationDate',
                '-DateTimeOriginal',
                str(file_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Parse exiftool output
            for line in result.stdout.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()

                    # Look for Create Date and similar fields
                    if key in ['CreateDate', 'MediaCreateDate', 'TrackCreateDate', 'CreationDate', 'DateTimeOriginal']:
                        if value and value != '0000:00:00 00:00:00':
                            try:
                                # Handle exiftool date format: "2022:09:11 16:21:51"
                                return datetime.strptime(value, "%Y:%m:%d %H:%M:%S"), False
                            except ValueError:
                                # Try alternative formats
                                for fmt in [
                                    "%Y-%m-%d %H:%M:%S",
                                    "%Y/%m/%d %H:%M:%S",
                                    "%Y:%m:%d %H:%M:%S%z",
                                    "%Y-%m-%dT%H:%M:%S",
                                    "%Y-%m-%dT%H:%M:%SZ"
                                ]:
                                    try:
                                        return datetime.strptime(value, fmt), False
                                    except ValueError:
                                        continue

            return None, False

        except subprocess.CalledProcessError as e:
            self.logger.warning(f"exiftool failed for {file_path}: {e}")
            return None, True
        except Exception as e:
            self.logger.warning(f"Error reading metadata from {file_path}: {e}")
            return None, True

    def _extract_metadata_ffprobe(self, file_path: Path) -> tuple[Optional[datetime], bool]:
        """Extract creation date from video metadata using ffprobe."""
        try:
            # Use ffprobe to extract metadata
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                str(file_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            metadata = json.loads(result.stdout)

            # Look for creation time in various fields
            format_info = metadata.get('format', {})
            tags = format_info.get('tags', {})

            # Common creation date fields in video metadata
            date_fields = [
                'creation_time',
                'date',
                'com.apple.quicktime.creationdate',
                'com.apple.quicktime.make',
                'DATE_DIGITIZED',
                'DATE'
            ]

            for field in date_fields:
                # Check both lowercase and uppercase variants
                for key in [field, field.lower(), field.upper()]:
                    if key in tags:
                        date_str = tags[key].strip()
                        if date_str and date_str != '0000-00-00T00:00:00.000000Z':
                            try:
                                # Handle various date formats
                                for fmt in [
                                    "%Y-%m-%dT%H:%M:%S.%fZ",
                                    "%Y-%m-%dT%H:%M:%SZ",
                                    "%Y-%m-%d %H:%M:%S",
                                    "%Y:%m:%d %H:%M:%S",
                                    "%Y-%m-%d"
                                ]:
                                    try:
                                        return datetime.strptime(date_str, fmt), False
                                    except ValueError:
                                        continue
                            except Exception:
                                continue

            return None, False

        except subprocess.CalledProcessError as e:
            self.logger.warning(f"ffprobe failed for {file_path}: {e}")
            return None, True
        except Exception as e:
            self.logger.warning(f"Error reading metadata from {file_path}: {e}")
            return None, True

    def get_file_modification_date(self, file_path: Path) -> datetime:
        """Get file modification date as fallback."""
        return datetime.fromtimestamp(file_path.stat().st_mtime)

    def generate_target_path(self, file_path: Path, date_taken: datetime) -> Path:
        """Generate the target path based on date taken."""
        year = date_taken.strftime("%Y")
        month = date_taken.strftime("%m")  # Just the month number: "06"

        # Create timestamp for filename
        timestamp = date_taken.strftime("%Y%m%d_%H%M%S")

        # Get original filename without extension
        original_name = file_path.stem
        original_name = self.sanitize_filename(original_name)

        # Build new filename with timestamp
        filename = f"{timestamp}{file_path.suffix}"
        filename = self.sanitize_filename(filename)

        return self.target_dir / year / month / filename

    def find_video_files(self) -> List[Path]:
        """Recursively find all video files in source directory."""
        video_files = []

        for file_path in self.source_dir.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_FORMATS:
                video_files.append(file_path)

        return video_files

    def move_file(self, source: Path, target: Path) -> bool:
        """Move file to target location, creating directories as needed."""
        try:
            if self.dry_run:
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

            # Create target directory
            target.parent.mkdir(parents=True, exist_ok=True)

            shutil.move(str(source), str(target))
            self.logger.info(f"Moved: {source.name} -> {target}")
            return True

        except Exception as e:
            self.logger.error(f"Error moving {source} to {target}: {e}")
            return False

    def organize_videos(self) -> Dict[str, int]:
        """Main method to organize all video files."""
        self.logger.info(f"Starting video organization...")
        self.logger.info(f"Source: {self.source_dir}")
        self.logger.info(f"Target: {self.target_dir}")
        self.logger.info(f"Dry run: {self.dry_run}")

        video_files = self.find_video_files()
        self.logger.info(f"Found {len(video_files)} video files")

        for file_path in video_files:
            self.stats['processed'] += 1

            # Try to extract metadata date
            date_taken, had_error = self.extract_video_metadata(file_path)

            if had_error:
                self.stats['errors'] += 1
                continue

            if date_taken is None:
                # Use file modification date as fallback
                date_taken = self.get_file_modification_date(file_path)
                self.logger.info(f"Using modification date for {file_path.name}")

            target_path = self.generate_target_path(file_path, date_taken)

            if self.move_file(file_path, target_path):
                self.stats['moved'] += 1
            else:
                self.stats['errors'] += 1

        self.logger.info("Organization complete!")
        self.logger.info(f"Statistics: {self.stats}")
        return self.stats

    @staticmethod
    def print_video_metadata(file_path: Path, use_ffprobe: bool = False):
        """Print all metadata for a given video file using exiftool or ffprobe."""
        try:
            if use_ffprobe:
                cmd = [
                    'ffprobe',
                    '-v', 'quiet',
                    '-print_format', 'json',
                    '-show_format',
                    '-show_streams',
                    str(file_path)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                metadata = json.loads(result.stdout)
                print(f"Metadata for {file_path.name} (using ffprobe):")
                print(json.dumps(metadata, indent=2))
            else:
                cmd = ['exiftool', str(file_path)]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                print(f"Metadata for {file_path.name} (using exiftool):")
                print(result.stdout)
        except Exception as e:
            print(f"Error reading metadata from {file_path}: {e}")


def main():
    """Command line interface."""
    parser = argparse.ArgumentParser(
        description="Organize videos by metadata date into Year/Month folders using exiftool or ffprobe",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python sort_videos.py /path/to/videos /path/to/organized --dry-run
  python sort_videos.py /path/to/videos /path/to/organized --ffprobe
  python sort_videos.py --metadata /path/to/video.mp4
  python sort_videos.py --metadata /path/to/video.mp4 --ffprobe
        """
    )

    parser.add_argument('source_dir', nargs='?',
                      help='Source directory containing video files')
    parser.add_argument('target_dir', nargs='?',
                      help='Target directory for organized videos')
    parser.add_argument('--dry-run', action='store_true',
                      help='Show what would be done without actually moving files')
    parser.add_argument('--ffprobe', action='store_true',
                      help='Use ffprobe instead of exiftool for metadata extraction')
    parser.add_argument('--metadata', metavar='FILE',
                      help='Print metadata for a specific video file')

    args = parser.parse_args()

    if args.metadata:
        VideoOrganizer.print_video_metadata(Path(args.metadata), args.ffprobe)
        return

    if not args.source_dir or not args.target_dir:
        parser.error("source_dir and target_dir are required unless using --metadata")

    try:
        organizer = VideoOrganizer(args.source_dir, args.target_dir, args.dry_run, args.ffprobe)
        stats = organizer.organize_videos()

        print(f"\nFinal Statistics:")
        print(f"  Processed: {stats['processed']}")
        print(f"  Moved: {stats['moved']}")
        print(f"  Errors: {stats['errors']}")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())