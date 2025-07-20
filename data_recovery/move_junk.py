#!/usr/bin/env python3
"""
File Extension Organizer

This script recursively finds files with specified extensions and moves them
into organized directories by file type. Useful for organizing recovered files
from data recovery tools like PhotoRec.
"""

import os
import shutil
import argparse
import hashlib
from pathlib import Path
from typing import List, Dict
import logging


class FileExtensionOrganizer:
    """Organizes files by extension into separate directories."""

    def __init__(self, source_dir: str, output_dir: str, extensions: List[str], dry_run: bool = False, copy: bool = False, check_space: bool = False, max_files: int = None, batch_size: int = 100, allow_sudo: bool = False, skip_duplicates: bool = False, remove_source_dupes: bool = False, dedupe_method: str = 'size'):
        self.source_dir = Path(source_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.extensions = {ext.lower().lstrip('.') for ext in extensions}  # Normalize extensions
        self.dry_run = dry_run
        self.copy = copy
        self.check_space = check_space
        self.max_files = max_files
        self.batch_size = batch_size
        self.allow_sudo = allow_sudo
        self.skip_duplicates = skip_duplicates
        self.remove_source_dupes = remove_source_dupes
        self.dedupe_method = dedupe_method
        self.sudo_available = False
        self.stats = {
            'processed': 0,
            'moved': 0,
            'errors': 0,
            'skipped_space': 0,
            'sudo_used': 0,
            'duplicates_skipped': 0,
            'duplicates_removed': 0,
            'by_extension': {}
        }

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def get_disk_usage(self, path: Path) -> Dict[str, int]:
        """Get disk usage statistics for a given path."""
        try:
            statvfs = os.statvfs(path)
            total = statvfs.f_frsize * statvfs.f_blocks
            free = statvfs.f_frsize * statvfs.f_bavail
            used = total - free

            return {
                'total': total,
                'used': used,
                'free': free
            }
        except Exception as e:
            self.logger.error(f"Error getting disk usage for {path}: {e}")
            return {'total': 0, 'used': 0, 'free': 0}

    def format_bytes(self, bytes_val: int) -> str:
        """Format bytes into human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f} PB"

    def check_available_space(self, files_to_process: List[Path]) -> bool:
        """Check if there's enough space for the operation."""
        if not self.check_space or self.dry_run:
            return True

        # Calculate total size of files to process
        total_size = 0
        for file_path in files_to_process:
            try:
                total_size += file_path.stat().st_size
            except Exception as e:
                self.logger.warning(f"Could not get size of {file_path}: {e}")

        # Get available space on target device
        disk_usage = self.get_disk_usage(self.output_dir.parent if self.output_dir.exists() else self.output_dir)
        available_space = disk_usage['free']

        # Add 10% buffer for safety
        required_space = total_size * 1.1 if self.copy else total_size * 0.1  # Less space needed for move

        self.logger.info(f"Total files size: {self.format_bytes(total_size)}")
        self.logger.info(f"Available space: {self.format_bytes(available_space)}")
        self.logger.info(f"Required space (with buffer): {self.format_bytes(int(required_space))}")

        if available_space < required_space:
            self.logger.error(f"Insufficient disk space! Need {self.format_bytes(int(required_space))}, "
                            f"but only {self.format_bytes(available_space)} available")
            return False

        return True

    def get_file_size_safely(self, file_path: Path) -> int:
        """Get file size safely, returning 0 if there's an error."""
        try:
            return file_path.stat().st_size
        except Exception:
            return 0

    def find_files_by_extensions(self) -> Dict[str, List[Path]]:
        """Find all files with the specified extensions."""
        files_by_ext = {ext: [] for ext in self.extensions}

        self.logger.info(f"Scanning {self.source_dir} for files with extensions: {', '.join(self.extensions)}")

        for file_path in self.source_dir.rglob('*'):
            if file_path.is_file():
                # Get extension without the dot and normalize to lowercase
                file_ext = file_path.suffix.lower().lstrip('.')

                if file_ext in self.extensions:
                    files_by_ext[file_ext].append(file_path)
                    self.stats['processed'] += 1

        # Log what we found
        for ext, files in files_by_ext.items():
            count = len(files)
            self.stats['by_extension'][ext] = count
            self.logger.info(f"Found {count} .{ext} files")

        return files_by_ext

    def create_output_directories(self) -> Dict[str, Path]:
        """Create output directories for each extension."""
        output_dirs = {}

        for ext in self.extensions:
            ext_dir = self.output_dir / f"{ext}_files"
            output_dirs[ext] = ext_dir

            if not self.dry_run:
                ext_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created directory: {ext_dir}")
            else:
                self.logger.info(f"DRY RUN: Would create directory: {ext_dir}")

        return output_dirs

    def move_file(self, source: Path, target_dir: Path) -> bool:
        """Move a file to the target directory, handling name conflicts and permissions."""
        try:
            target_file = target_dir / source.name

            # Handle name conflicts by adding a number suffix
            if target_file.exists():
                counter = 1
                stem = source.stem
                suffix = source.suffix

                while target_file.exists():
                    target_file = target_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

                self.logger.warning(f"File conflict resolved: {source.name} -> {target_file.name}")

            if self.dry_run:
                self.logger.info(f"DRY RUN: Would move {source} -> {target_file}")
                return True

            # Try normal operation first
            try:
                if self.copy:
                    shutil.copy2(str(source), str(target_file))
                    self.logger.debug(f"Copied: {source} -> {target_file}")
                else:
                    shutil.move(str(source), str(target_file))
                    self.logger.debug(f"Moved: {source} -> {target_file}")
                return True
            except PermissionError as e:
                # Permission denied - try with sudo if allowed
                if self.allow_sudo and self.sudo_available:
                    return self.move_file_with_sudo(source, target_file)
                else:
                    self.logger.error(f"Permission denied moving {source}: {e}")
                    if self.allow_sudo:
                        self.logger.error("Try running with --sudo flag for elevated permissions")
                    return False

        except Exception as e:
            self.logger.error(f"Error moving {source}: {e}")
            return False

    def move_file_with_sudo(self, source: Path, target_file: Path) -> bool:
        """Move a file using sudo if necessary."""
        try:
            import subprocess
            if self.copy:
                cmd = ['sudo', 'cp', '-p', str(source), str(target_file)]
            else:
                cmd = ['sudo', 'mv', str(source), str(target_file)]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                self.logger.debug(f"Used sudo to move: {source} -> {target_file}")
                self.stats['sudo_used'] += 1
                return True
            else:
                self.logger.error(f"Sudo operation failed: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Error with sudo operation: {e}")
            return False

    def get_file_hash(self, file_path: Path, method: str = 'md5') -> str:
        """Calculate file hash for duplicate detection."""
        try:
            if method == 'md5':
                hash_obj = hashlib.md5()
            elif method == 'sha256':
                hash_obj = hashlib.sha256()
            else:
                return ""

            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception as e:
            self.logger.warning(f"Could not calculate hash for {file_path}: {e}")
            return ""

    def files_are_identical(self, file1: Path, file2: Path) -> bool:
        """Check if two files are identical using the selected method."""
        try:
            if self.dedupe_method == 'size':
                # Quick size comparison
                return file1.stat().st_size == file2.stat().st_size
            elif self.dedupe_method == 'hash':
                # More thorough hash comparison
                return self.get_file_hash(file1) == self.get_file_hash(file2)
            elif self.dedupe_method == 'both':
                # Size first (fast), then hash if sizes match
                if file1.stat().st_size != file2.stat().st_size:
                    return False
                return self.get_file_hash(file1) == self.get_file_hash(file2)
        except Exception as e:
            self.logger.warning(f"Error comparing files {file1} and {file2}: {e}")
            return False

        return False

    def organize_files(self) -> Dict[str, int]:
        """Main method to organize all files by extension."""
        self.logger.info("Starting file organization by extension...")
        self.logger.info(f"Source: {self.source_dir}")
        self.logger.info(f"Output: {self.output_dir}")
        self.logger.info(f"Extensions: {', '.join(self.extensions)}")
        self.logger.info(f"Dry run: {self.dry_run}")
        self.logger.info(f"Copy files: {self.copy}")
        self.logger.info(f"Check space: {self.check_space}")
        self.logger.info(f"Max files: {self.max_files}")
        self.logger.info(f"Batch size: {self.batch_size}")

        # Find all files
        files_by_ext = self.find_files_by_extensions()

        if self.stats['processed'] == 0:
            self.logger.warning("No files found with the specified extensions!")
            return self.stats

        # Create output directories
        output_dirs = self.create_output_directories()

        # Move files
        for ext, files in files_by_ext.items():
            if not files:
                continue

            target_dir = output_dirs[ext]
            self.logger.info(f"Moving {len(files)} .{ext} files to {target_dir}")

            # Check available space before processing
            if not self.check_available_space(files):
                self.logger.warning(f"Skipping .{ext} files due to insufficient space")
                self.stats['skipped_space'] += len(files)
                continue

            # Process files in batches
            for i in range(0, len(files), self.batch_size):
                if self.max_files and self.stats['moved'] >= self.max_files:
                    self.logger.info(f"Reached maximum file limit ({self.max_files}), stopping.")
                    break

                batch = files[i:i+self.batch_size]

                for file_path in batch:
                    # Skip duplicates if the option is enabled
                    if self.skip_duplicates:
                        # Check for duplicates in the target directory
                        is_duplicate = any(self.files_are_identical(file_path, existing_file) for existing_file in output_dirs[ext].glob('*'))
                        if is_duplicate:
                            self.logger.info(f"Duplicate file detected: {file_path.name}")
                            self.stats['duplicates_skipped'] += 1

                            # Remove the duplicate from source if requested
                            if self.remove_source_dupes:
                                if self.remove_duplicate_file(file_path):
                                    self.stats['duplicates_removed'] += 1
                            continue

                    if self.move_file(file_path, target_dir):
                        self.stats['moved'] += 1
                    else:
                        self.stats['errors'] += 1

        self.logger.info("Organization complete!")
        self.logger.info(f"Statistics: {self.stats}")

        return self.stats

    def cleanup_empty_directories(self):
        """Remove empty directories left behind after moving files."""
        if self.dry_run:
            self.logger.info("DRY RUN: Would clean up empty directories")
            return

        self.logger.info("Cleaning up empty directories...")

        # Walk from bottom up to remove empty directories
        for dirpath, dirnames, filenames in os.walk(self.source_dir, topdown=False):
            dir_path = Path(dirpath)

            # Skip the source directory itself
            if dir_path == self.source_dir:
                continue

            try:
                # Only remove if directory is empty
                if not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    self.logger.debug(f"Removed empty directory: {dir_path}")
            except OSError as e:
                # Directory not empty or permission error
                self.logger.debug(f"Could not remove directory {dir_path}: {e}")

    def check_permissions(self) -> bool:
        """Check if we have necessary permissions for the operation."""
        # Check source directory read permissions
        if not os.access(self.source_dir, os.R_OK):
            self.logger.error(f"No read permission for source directory: {self.source_dir}")
            return False

        # Check if we can create the output directory
        try:
            if not self.output_dir.exists():
                # Try to create the output directory to test permissions
                if not self.dry_run:
                    self.output_dir.mkdir(parents=True, exist_ok=True)
                else:
                    # In dry run, just check parent directory write permissions
                    parent = self.output_dir.parent
                    if not os.access(parent, os.W_OK):
                        self.logger.error(f"No write permission for output parent directory: {parent}")
                        return False
            else:
                # Check write permissions on existing directory
                if not os.access(self.output_dir, os.W_OK):
                    self.logger.error(f"No write permission for output directory: {self.output_dir}")
                    return False
        except PermissionError as e:
            self.logger.error(f"Permission denied creating output directory: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error checking output directory permissions: {e}")
            return False

        return True

    def check_sudo_available(self) -> bool:
        """Check if sudo is available and user can use it."""
        try:
            import subprocess
            result = subprocess.run(['sudo', '-n', 'true'],
                                  capture_output=True,
                                  timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    def request_sudo_if_needed(self) -> bool:
        """Request sudo privileges if needed for the operation."""
        # If sudo is explicitly requested, always set it up
        if self.allow_sudo:
            self.logger.info("Sudo access requested. Setting up elevated privileges...")

            # Check if we're already running with elevated privileges
            if os.geteuid() == 0:
                self.logger.info("Already running with root privileges.")
                self.sudo_available = True
                return True

            # Check if sudo is available
            if not self.check_sudo_available():
                # Try to authenticate with sudo
                try:
                    import subprocess
                    result = subprocess.run(['sudo', 'true'], timeout=30)
                    if result.returncode != 0:
                        self.logger.error("Failed to obtain sudo privileges.")
                        return False
                except subprocess.TimeoutExpired:
                    self.logger.error("Sudo authentication timed out.")
                    return False
                except Exception as e:
                    self.logger.error(f"Error during sudo authentication: {e}")
                    return False

            self.logger.info("Sudo privileges obtained successfully.")
            self.sudo_available = True
            return True

        # If no sudo requested, just check basic permissions
        return self.check_permissions()

    def remove_duplicate_file(self, file_path: Path) -> bool:
        """Remove a duplicate file from the source directory."""
        try:
            if self.dry_run:
                self.logger.info(f"DRY RUN: Would remove duplicate file: {file_path}")
                return True

            # Try normal removal first
            try:
                file_path.unlink()
                self.logger.info(f"Removed duplicate file: {file_path}")
                return True
            except PermissionError as e:
                # Permission denied - try with sudo if allowed
                if self.allow_sudo and self.sudo_available:
                    return self.remove_file_with_sudo(file_path)
                else:
                    self.logger.error(f"Permission denied removing {file_path}: {e}")
                    if self.allow_sudo:
                        self.logger.error("Try running with --sudo flag for elevated permissions")
                    return False
        except Exception as e:
            self.logger.error(f"Error removing duplicate file {file_path}: {e}")
            return False

    def remove_file_with_sudo(self, file_path: Path) -> bool:
        """Remove a file using sudo if necessary."""
        try:
            import subprocess
            cmd = ['sudo', 'rm', str(file_path)]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                self.logger.info(f"Used sudo to remove duplicate file: {file_path}")
                self.stats['sudo_used'] += 1
                return True
            else:
                self.logger.error(f"Sudo removal failed: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Error with sudo removal operation: {e}")
            return False
def main():
    """Command line interface."""
    parser = argparse.ArgumentParser(
        description="Organize files by extension into separate directories",
        epilog="""
Examples:
  %(prog)s py java c          # Organize .py, .java, and .c files
  %(prog)s py --output ./organized --dry-run
  %(prog)s jpg png gif --source ./recovered_photos --cleanup
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'extensions',
        nargs='+',
        help='File extensions to organize (without the dot, e.g., py java c)'
    )

    parser.add_argument(
        '--source',
        default='.',
        help='Source directory to scan (default: current directory)'
    )

    parser.add_argument(
        '--output',
        default='./organized_files',
        help='Output directory for organized files (default: ./organized_files)'
    )

    parser.add_argument(
        '--copy',
        action='store_true',
        help='Copy files instead of moving them (uses more space but safer)'
    )

    parser.add_argument(
        '--check-space',
        action='store_true',
        help='Check available disk space before operations'
    )

    parser.add_argument(
        '--max-files',
        type=int,
        help='Maximum number of files to process (useful for limited space)'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Process files in batches of this size (default: 100)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually moving files'
    )

    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Remove empty directories after moving files'
    )

    parser.add_argument(
        '--sudo',
        action='store_true',
        help='Allow sudo elevation if needed for permission issues'
    )

    parser.add_argument(
        '--skip-duplicates',
        action='store_true',
        help='Skip files that are duplicates of already processed files'
    )

    parser.add_argument(
        '--remove-source-dupes',
        action='store_true',
        help='Remove duplicate files from source directory (requires --skip-duplicates)'
    )

    parser.add_argument(
        '--dedupe-method',
        choices=['size', 'hash', 'both'],
        default='size',
        help='Method for detecting duplicates: size (fast), hash (thorough), both (size+hash)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate argument combinations
    if args.remove_source_dupes and not args.skip_duplicates:
        print("Error: --remove-source-dupes requires --skip-duplicates to be enabled")
        return 1

    # Validate source directory
    source_path = Path(args.source)
    if not source_path.exists():
        print(f"Error: Source directory '{source_path}' does not exist")
        return 1

    if not source_path.is_dir():
        print(f"Error: '{source_path}' is not a directory")
        return 1

    # Create organizer and run
    organizer = FileExtensionOrganizer(
        args.source,
        args.output,
        args.extensions,
        args.dry_run,
        args.copy,
        args.check_space,
        args.max_files,
        args.batch_size,
        args.sudo,
        args.skip_duplicates,
        args.remove_source_dupes,
        args.dedupe_method
    )

    # Check permissions and request sudo if needed
    if args.sudo:
        if not organizer.request_sudo_if_needed():
            print("Error: Cannot proceed without necessary permissions.")
            return 1
    elif not organizer.check_permissions():
        print("Error: Insufficient permissions. Try running with --sudo flag.")
        return 1

    stats = organizer.organize_files()

    # Clean up empty directories if requested
    if args.cleanup:
        organizer.cleanup_empty_directories()

    # Print summary
    print("\n" + "="*60)
    print("FILE ORGANIZATION SUMMARY")
    print("="*60)
    print(f"Total files processed: {stats['processed']}")
    print(f"Files moved: {stats['moved']}")
    print(f"Errors: {stats['errors']}")

    if stats['duplicates_skipped'] > 0:
        print(f"Duplicates skipped: {stats['duplicates_skipped']}")

    if stats['duplicates_removed'] > 0:
        print(f"Duplicates removed from source: {stats['duplicates_removed']}")

    if stats['by_extension']:
        print("\nFiles by extension:")
        for ext, count in stats['by_extension'].items():
            print(f"  .{ext}: {count} files")

    if args.dry_run:
        print("\n" + "="*60)
        print("This was a dry run - no files were actually moved.")
        print("Remove --dry-run to perform the actual organization.")
    else:
        print(f"\nFiles organized into: {args.output}")
        if args.cleanup:
            print("Empty directories have been cleaned up.")

    return 0


if __name__ == "__main__":
    exit(main())
