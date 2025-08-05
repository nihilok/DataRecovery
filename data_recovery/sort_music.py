#!/usr/bin/env python3
"""
Music File Organizer

This script recursively finds MP3 and FLAC files, reads their ID3 tags,
and organizes them into a logical directory structure: Artist/Album/Track.
"""

import os
import shutil
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
import logging

try:
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.id3 import ID3NoHeaderError
    from mutagen import File as MutagenFile
except ImportError:
    print("Error: mutagen library not found. Please install with: pip install mutagen")
    exit(1)


class MusicOrganizer:
    """Organizes music files based on their metadata tags."""

    SUPPORTED_FORMATS = {'.mp3', '.flac', '.ogg', '.m4a', '.wav', '.ape'}

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

    def sanitize_filename(self, filename: str) -> str:
        """Remove or replace invalid characters for filesystem compatibility."""
        # Replace problematic characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Remove leading/trailing dots and spaces
        filename = filename.strip('. ')
        # Limit length
        if len(filename) > 200:
            filename = filename[:200]
        return filename or "Unknown"

    def extract_metadata(self, file_path: Path) -> Dict[str, str]:
        """Extract metadata from audio file."""
        try:
            audio_file = MutagenFile(file_path)
            if audio_file is None:
                return {}

            metadata = {}

            # Common tag mappings for different formats
            tag_mappings = {
                'artist': ['TPE1', 'ARTIST', 'albumartist', 'TPE2'],
                'album': ['TALB', 'ALBUM'],
                'title': ['TIT2', 'TITLE'],
                'track': ['TRCK', 'TRACKNUMBER'],
                'date': ['TDRC', 'DATE', 'YEAR'],
                'genre': ['TCON', 'GENRE']
            }

            for key, possible_tags in tag_mappings.items():
                for tag in possible_tags:
                    if tag in audio_file:
                        value = audio_file[tag]
                        if isinstance(value, list) and value:
                            metadata[key] = str(value[0])
                        else:
                            metadata[key] = str(value)
                        break

            return metadata

        except Exception as e:
            self.logger.warning(f"Error reading metadata from {file_path}: {e}")
            return {}

    def generate_target_path(self, file_path: Path, metadata: Dict[str, str]) -> Path:
        """Generate the target path based on metadata."""
        artist = metadata.get('artist', 'Unknown Artist')
        album = metadata.get('album', 'Unknown Album')
        title = metadata.get('title', file_path.stem)
        track = metadata.get('track', '')

        # Clean track number (remove total tracks if present, e.g., "1/12" -> "01")
        if track and '/' in track:
            track = track.split('/')[0]

        # Pad track number with zero if it's numeric
        if track.isdigit():
            track = f"{int(track):02d}"

        # Sanitize all components
        artist = self.sanitize_filename(artist)
        album = self.sanitize_filename(album)
        title = self.sanitize_filename(title)

        # Build filename
        if track:
            filename = f"{track} - {title}{file_path.suffix}"
        else:
            filename = f"{title}{file_path.suffix}"

        filename = self.sanitize_filename(filename)

        return self.target_dir / artist / album / filename

    def find_music_files(self) -> List[Path]:
        """Recursively find all music files in source directory."""
        music_files = []

        for file_path in self.source_dir.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_FORMATS:
                music_files.append(file_path)

        return music_files

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

    def organize_music(self) -> Dict[str, int]:
        """Main method to organize all music files."""
        self.logger.info(f"Starting music organization...")
        self.logger.info(f"Source: {self.source_dir}")
        self.logger.info(f"Target: {self.target_dir}")
        self.logger.info(f"Dry run: {self.dry_run}")

        music_files = self.find_music_files()
        self.logger.info(f"Found {len(music_files)} music files")

        for file_path in music_files:
            self.stats['processed'] += 1

            try:
                metadata = self.extract_metadata(file_path)
                target_path = self.generate_target_path(file_path, metadata)

                if self.move_file(file_path, target_path):
                    self.stats['moved'] += 1
                else:
                    self.stats['errors'] += 1

            except Exception as e:
                self.logger.error(f"Error processing {file_path}: {e}")
                self.stats['errors'] += 1

        self.logger.info("Organization complete!")
        self.logger.info(f"Statistics: {self.stats}")

        return self.stats


def main():
    """Command line interface."""
    parser = argparse.ArgumentParser(
        description="Organize music files by artist and album using ID3 tags"
    )
    parser.add_argument(
        "source",
        help="Source directory containing music files"
    )
    parser.add_argument(
        "target",
        help="Target directory for organized music"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually moving files"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate directories
    source_path = Path(args.source)
    if not source_path.exists():
        print(f"Error: Source directory '{source_path}' does not exist")
        return 1

    # Create organizer and run
    organizer = MusicOrganizer(args.source, args.target, args.dry_run)
    stats = organizer.organize_music()

    # Print summary
    print("\n" + "="*50)
    print("ORGANIZATION SUMMARY")
    print("="*50)
    print(f"Files processed: {stats['processed']}")
    print(f"Files moved: {stats['moved']}")
    print(f"Files skipped: {stats['skipped']}")
    print(f"Errors: {stats['errors']}")

    if args.dry_run:
        print("\nThis was a dry run - no files were actually moved.")
        print("Remove --dry-run to perform the actual organization.")

    return 0


if __name__ == "__main__":
    exit(main())
