#!/usr/bin/env python3
"""
Split a large directory of files into subdirectories with maximum size limit.

This script takes a source directory and splits its files into multiple
subdirectories, each not exceeding the specified size limit (default 1GB).
"""

import os
import shutil
from pathlib import Path
from typing import List, Tuple, Optional
import argparse
import logging
from collections import defaultdict


class FileSplitter:
    """Split files from a source directory into size-limited subdirectories."""

    def __init__(self, max_size_gb: float = 1.0, dry_run: bool = False):
        """
        Initialize the FileSplitter.

        Args:
            max_size_gb: Maximum size per subdirectory in GB
            dry_run: If True, only simulate the operation without moving files
        """
        self.max_size_bytes = int(max_size_gb * 1024 * 1024 * 1024)  # Convert GB to bytes
        self.dry_run = dry_run
        self.logger = self._setup_logging()

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)

    def get_file_size(self, file_path: Path) -> int:
        """Get the size of a file in bytes."""
        try:
            return file_path.stat().st_size
        except (OSError, FileNotFoundError) as e:
            self.logger.error(f"Error getting size for {file_path}: {e}")
            return 0

    def scan_directory(self, source_dir: Path) -> List[Tuple[Path, int]]:
        """
        Scan directory and return list of (file_path, file_size) tuples.

        Args:
            source_dir: Path to the source directory

        Returns:
            List of tuples containing file path and size
        """
        files = []
        if not source_dir.exists() or not source_dir.is_dir():
            raise ValueError(f"Source directory does not exist or is not a directory: {source_dir}")

        for file_path in source_dir.iterdir():
            if file_path.is_file():
                size = self.get_file_size(file_path)
                if size > 0:  # Only include files with valid size
                    files.append((file_path, size))

        # Sort by size (largest first) for better packing
        files.sort(key=lambda x: x[1], reverse=True)
        return files

    def calculate_splits(self, files: List[Tuple[Path, int]]) -> List[List[Tuple[Path, int]]]:
        """
        Calculate how to split files into subdirectories using a greedy algorithm.

        Args:
            files: List of (file_path, file_size) tuples

        Returns:
            List of lists, each representing files for one subdirectory
        """
        splits = []
        current_split = []
        current_size = 0

        for file_path, file_size in files:
            # Check if single file exceeds max size
            if file_size > self.max_size_bytes:
                self.logger.warning(
                    f"File {file_path.name} ({file_size / (1024**3):.2f} GB) "
                    f"exceeds maximum size limit ({self.max_size_bytes / (1024**3):.2f} GB). "
                    f"It will be placed in its own directory."
                )
                # If we have files in current split, finalize it
                if current_split:
                    splits.append(current_split)
                    current_split = []
                    current_size = 0
                # Add the large file to its own split
                splits.append([(file_path, file_size)])
                continue

            # Check if adding this file would exceed the limit
            if current_size + file_size > self.max_size_bytes:
                # Finalize current split and start a new one
                if current_split:
                    splits.append(current_split)
                current_split = [(file_path, file_size)]
                current_size = file_size
            else:
                # Add file to current split
                current_split.append((file_path, file_size))
                current_size += file_size

        # Don't forget the last split
        if current_split:
            splits.append(current_split)

        return splits

    def create_output_directories(self, output_dir: Path, num_splits: int) -> List[Path]:
        """
        Create output subdirectories.

        Args:
            output_dir: Base output directory
            num_splits: Number of subdirectories to create

        Returns:
            List of created directory paths
        """
        directories = []

        if not self.dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)

        for i in range(num_splits):
            subdir = output_dir / f"batch_{i+1:03d}"
            if not self.dry_run:
                subdir.mkdir(exist_ok=True)
            directories.append(subdir)

        return directories

    def move_files(self, splits: List[List[Tuple[Path, int]]], output_dirs: List[Path]) -> None:
        """
        Move files to their respective output directories.

        Args:
            splits: List of file splits
            output_dirs: List of output directory paths
        """
        for i, (split, output_dir) in enumerate(zip(splits, output_dirs)):
            total_size = sum(size for _, size in split)
            self.logger.info(
                f"Processing batch {i+1}/{len(splits)}: "
                f"{len(split)} files, {total_size / (1024**3):.2f} GB -> {output_dir}"
            )

            for file_path, file_size in split:
                destination = output_dir / file_path.name

                # Handle duplicate filenames
                counter = 1
                original_destination = destination
                while destination.exists():
                    stem = original_destination.stem
                    suffix = original_destination.suffix
                    destination = output_dir / f"{stem}_{counter:03d}{suffix}"
                    counter += 1

                if self.dry_run:
                    self.logger.info(f"  [DRY RUN] Would move: {file_path} -> {destination}")
                else:
                    try:
                        shutil.move(str(file_path), str(destination))
                        self.logger.info(f"  Moved: {file_path.name} -> {destination}")
                    except (OSError, shutil.Error) as e:
                        self.logger.error(f"  Error moving {file_path} to {destination}: {e}")

    def split_directory(self, source_dir: Path, output_dir: Path) -> None:
        """
        Main method to split a directory into size-limited subdirectories.

        Args:
            source_dir: Path to source directory containing files to split
            output_dir: Path to output directory where subdirectories will be created
        """
        self.logger.info(f"Starting directory split: {source_dir} -> {output_dir}")
        self.logger.info(f"Maximum size per subdirectory: {self.max_size_bytes / (1024**3):.2f} GB")

        # Scan source directory
        files = self.scan_directory(source_dir)
        if not files:
            self.logger.warning("No files found in source directory")
            return

        total_size = sum(size for _, size in files)
        self.logger.info(f"Found {len(files)} files, total size: {total_size / (1024**3):.2f} GB")

        # Calculate splits
        splits = self.calculate_splits(files)
        self.logger.info(f"Files will be split into {len(splits)} subdirectories")

        # Create output directories
        output_dirs = self.create_output_directories(output_dir, len(splits))

        # Move files
        self.move_files(splits, output_dirs)

        self.logger.info("Directory split completed successfully")

    def get_statistics(self, source_dir: Path) -> dict:
        """
        Get statistics about the files in the source directory.

        Args:
            source_dir: Path to source directory

        Returns:
            Dictionary containing file statistics
        """
        files = self.scan_directory(source_dir)

        if not files:
            return {"total_files": 0, "total_size_gb": 0, "file_types": {}}

        total_size = sum(size for _, size in files)
        file_types = defaultdict(int)

        for file_path, _ in files:
            extension = file_path.suffix.lower() or "no_extension"
            file_types[extension] += 1

        return {
            "total_files": len(files),
            "total_size_gb": total_size / (1024**3),
            "file_types": dict(file_types),
            "estimated_subdirs": len(self.calculate_splits(files))
        }

    def flatten_directory(self, source_dir: Path, output_dir: Path) -> None:
        """
        Move all files from subdirectories of source_dir into output_dir, flattening the structure.
        Args:
            source_dir: Directory containing batch subdirectories
            output_dir: Target directory to move all files into
        """
        self.logger.info(f"Flattening files from {source_dir} into {output_dir}")
        if not self.dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)
        moved = 0
        for subdir in source_dir.iterdir():
            if subdir.is_dir():
                for file_path in subdir.iterdir():
                    if file_path.is_file():
                        destination = output_dir / file_path.name
                        # Handle duplicate filenames
                        counter = 1
                        original_destination = destination
                        while destination.exists():
                            stem = original_destination.stem
                            suffix = original_destination.suffix
                            destination = output_dir / f"{stem}_{counter:03d}{suffix}"
                            counter += 1
                        if self.dry_run:
                            self.logger.info(f"  [DRY RUN] Would move: {file_path} -> {destination}")
                        else:
                            try:
                                shutil.move(str(file_path), str(destination))
                                self.logger.info(f"  Moved: {file_path.name} -> {destination}")
                                moved += 1
                            except (OSError, shutil.Error) as e:
                                self.logger.error(f"  Error moving {file_path} to {destination}: {e}")
        self.logger.info(f"Flattening completed. {moved} files moved.")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Split a directory of files into subdirectories with size limits"
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Source directory containing files to split"
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Output directory where subdirectories will be created"
    )
    parser.add_argument(
        "--max-size",
        type=float,
        default=1.0,
        help="Maximum size per subdirectory in GB (default: 1.0)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the operation without actually moving files"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics about the source directory and exit"
    )
    parser.add_argument(
        "--flatten",
        action="store_true",
        help="Flatten all files from batch subdirectories into the output directory (reverse operation)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.source.exists():
        print(f"Error: Source directory does not exist: {args.source}")
        return 1

    if not args.source.is_dir():
        print(f"Error: Source path is not a directory: {args.source}")
        return 1

    # Create splitter instance
    splitter = FileSplitter(max_size_gb=args.max_size, dry_run=args.dry_run)

    # Show statistics if requested
    if args.stats:
        stats = splitter.get_statistics(args.source)
        print(f"\nDirectory Statistics for: {args.source}")
        print(f"Total files: {stats['total_files']}")
        print(f"Total size: {stats['total_size_gb']:.2f} GB")
        print(f"Estimated subdirectories needed: {stats['estimated_subdirs']}")
        print("\nFile types:")
        for ext, count in sorted(stats['file_types'].items()):
            print(f"  {ext}: {count} files")
        return 0

    # Perform flatten if requested
    if args.flatten:
        try:
            splitter.flatten_directory(args.source, args.output)
            return 0
        except Exception as e:
            print(f"Error: {e}")
            return 1

    # Perform the split
    try:
        splitter.split_directory(args.source, args.output)
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
