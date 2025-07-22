#!/usr/bin/env python3
"""
Deduplicate files by content hash across directories.

This script finds duplicate files by comparing their SHA-256 hashes and removes
duplicates, keeping only one copy of each unique file. It's particularly useful
for cleaning up duplicate photos across multiple batch directories.
"""

import os
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
import argparse
import logging
from collections import defaultdict
import json
import time


class FileDuplicateRemover:
    """Find and remove duplicate files based on content hash."""
    
    def __init__(self, dry_run: bool = False, hash_algorithm: str = "sha256"):
        """
        Initialize the duplicate remover.
        
        Args:
            dry_run: If True, only report what would be done without actual removal
            hash_algorithm: Hash algorithm to use (sha256, md5, sha1)
        """
        self.dry_run = dry_run
        self.hash_algorithm = hash_algorithm
        self.logger = self._setup_logging()
        self.file_hashes: Dict[str, List[Path]] = defaultdict(list)
        self.processed_files = 0
        self.total_files = 0
        self.duplicates_found = 0
        self.space_saved = 0
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def calculate_file_hash(self, file_path: Path, chunk_size: int = 8192) -> Optional[str]:
        """
        Calculate hash of a file.
        
        Args:
            file_path: Path to the file
            chunk_size: Size of chunks to read at a time (in bytes)
            
        Returns:
            Hex digest of the file hash, or None if error
        """
        try:
            hash_obj = hashlib.new(self.hash_algorithm)
            
            with open(file_path, 'rb') as f:
                while chunk := f.read(chunk_size):
                    hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
        
        except (OSError, IOError) as e:
            self.logger.error(f"Error reading file {file_path}: {e}")
            return None
    
    def scan_directory(self, directory: Path, include_patterns: Optional[List[str]] = None,
                      exclude_patterns: Optional[List[str]] = None, recursive: bool = True) -> None:
        """
        Scan directory for files and calculate their hashes.
        
        Args:
            directory: Directory to scan
            include_patterns: List of file patterns to include (e.g., ['*.jpg', '*.png'])
            exclude_patterns: List of file patterns to exclude
            recursive: Whether to scan subdirectories recursively
        """
        if not directory.exists() or not directory.is_dir():
            raise ValueError(f"Directory does not exist or is not a directory: {directory}")
        
        self.logger.info(f"Scanning directory: {directory}")
        
        # Get all files to process
        if recursive:
            all_files = [f for f in directory.rglob('*') if f.is_file()]
        else:
            all_files = [f for f in directory.iterdir() if f.is_file()]
        
        # Filter files based on patterns
        files_to_process = self._filter_files(all_files, include_patterns, exclude_patterns)
        
        self.total_files = len(files_to_process)
        self.logger.info(f"Found {self.total_files} files to process")
        
        # Process files
        for file_path in files_to_process:
            self._process_file(file_path)
    
    def _filter_files(self, files: List[Path], include_patterns: Optional[List[str]] = None,
                     exclude_patterns: Optional[List[str]] = None) -> List[Path]:
        """Filter files based on include/exclude patterns."""
        import fnmatch
        
        filtered_files = files
        
        # Apply include patterns
        if include_patterns:
            included_files = []
            for file_path in filtered_files:
                for pattern in include_patterns:
                    if fnmatch.fnmatch(file_path.name.lower(), pattern.lower()):
                        included_files.append(file_path)
                        break
            filtered_files = included_files
        
        # Apply exclude patterns
        if exclude_patterns:
            excluded_files = []
            for file_path in filtered_files:
                should_exclude = False
                for pattern in exclude_patterns:
                    if fnmatch.fnmatch(file_path.name.lower(), pattern.lower()):
                        should_exclude = True
                        break
                if not should_exclude:
                    excluded_files.append(file_path)
            filtered_files = excluded_files
        
        return filtered_files
    
    def _process_file(self, file_path: Path) -> None:
        """Process a single file and add to hash database."""
        file_hash = self.calculate_file_hash(file_path)
        if file_hash:
            self.file_hashes[file_hash].append(file_path)
            self.processed_files += 1
            
            if self.processed_files % 100 == 0 or self.processed_files == self.total_files:
                progress = (self.processed_files / self.total_files) * 100
                self.logger.info(f"Progress: {self.processed_files}/{self.total_files} ({progress:.1f}%)")
    
    def find_duplicates(self) -> Dict[str, List[Path]]:
        """
        Find files with identical hashes.
        
        Returns:
            Dictionary mapping hash to list of duplicate file paths
        """
        duplicates = {hash_val: paths for hash_val, paths in self.file_hashes.items() if len(paths) > 1}
        self.duplicates_found = sum(len(paths) - 1 for paths in duplicates.values())  # Total duplicates to remove
        
        self.logger.info(f"Found {len(duplicates)} sets of duplicates ({self.duplicates_found} files to remove)")
        return duplicates
    
    def choose_file_to_keep(self, duplicate_files: List[Path], strategy: str = "shortest_path") -> Path:
        """
        Choose which file to keep from a set of duplicates.
        
        Args:
            duplicate_files: List of duplicate file paths
            strategy: Strategy for choosing which file to keep:
                     - "shortest_path": Keep file with shortest path
                     - "oldest": Keep oldest file (by modification time)
                     - "newest": Keep newest file (by modification time)
                     - "largest_name": Keep file with longest filename
                     - "first_alphabetical": Keep first file alphabetically
        
        Returns:
            Path of the file to keep
        """
        if not duplicate_files:
            raise ValueError("No files provided")
        
        if len(duplicate_files) == 1:
            return duplicate_files[0]
        
        if strategy == "shortest_path":
            return min(duplicate_files, key=lambda f: len(str(f)))
        elif strategy == "oldest":
            return min(duplicate_files, key=lambda f: f.stat().st_mtime)
        elif strategy == "newest":
            return max(duplicate_files, key=lambda f: f.stat().st_mtime)
        elif strategy == "largest_name":
            return max(duplicate_files, key=lambda f: len(f.name))
        elif strategy == "first_alphabetical":
            return min(duplicate_files, key=lambda f: str(f).lower())
        else:
            self.logger.warning(f"Unknown strategy '{strategy}', using 'shortest_path'")
            return min(duplicate_files, key=lambda f: len(str(f)))
    
    def remove_duplicates(self, duplicates: Dict[str, List[Path]], 
                         keep_strategy: str = "shortest_path") -> None:
        """
        Remove duplicate files, keeping one copy of each.
        
        Args:
            duplicates: Dictionary of hash -> list of duplicate paths
            keep_strategy: Strategy for choosing which file to keep
        """
        self.logger.info(f"Removing duplicates using '{keep_strategy}' strategy")
        
        removed_count = 0
        
        for file_hash, duplicate_files in duplicates.items():
            # Choose which file to keep
            file_to_keep = self.choose_file_to_keep(duplicate_files, keep_strategy)
            files_to_remove = [f for f in duplicate_files if f != file_to_keep]
            
            self.logger.info(f"\nDuplicate set (hash: {file_hash[:16]}...):")
            self.logger.info(f"  KEEPING: {file_to_keep}")
            
            for file_to_remove in files_to_remove:
                file_size = file_to_remove.stat().st_size
                self.space_saved += file_size
                
                if self.dry_run:
                    self.logger.info(f"  [DRY RUN] Would remove: {file_to_remove} ({file_size / (1024**2):.1f} MB)")
                else:
                    try:
                        file_to_remove.unlink()
                        self.logger.info(f"  REMOVED: {file_to_remove} ({file_size / (1024**2):.1f} MB)")
                        removed_count += 1
                    except OSError as e:
                        self.logger.error(f"  ERROR removing {file_to_remove}: {e}")
        
        if not self.dry_run:
            self.logger.info(f"\nSuccessfully removed {removed_count} duplicate files")
        self.logger.info(f"Total space {'that would be ' if self.dry_run else ''}saved: {self.space_saved / (1024**3):.2f} GB")
    
    def generate_report(self, duplicates: Dict[str, List[Path]], output_file: Optional[Path] = None) -> str:
        """
        Generate a detailed report of duplicates found.
        
        Args:
            duplicates: Dictionary of duplicates
            output_file: Optional file to save the report
            
        Returns:
            Report as a string
        """
        report_lines = []
        report_lines.append("DUPLICATE FILES REPORT")
        report_lines.append("=" * 50)
        report_lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Total files scanned: {self.processed_files}")
        report_lines.append(f"Duplicate sets found: {len(duplicates)}")
        report_lines.append(f"Duplicate files to remove: {self.duplicates_found}")
        report_lines.append(f"Space to be saved: {self.space_saved / (1024**3):.2f} GB")
        report_lines.append("")
        
        for i, (file_hash, duplicate_files) in enumerate(duplicates.items(), 1):
            report_lines.append(f"Duplicate Set #{i}")
            report_lines.append(f"Hash: {file_hash}")
            report_lines.append(f"Files ({len(duplicate_files)}):")
            
            for file_path in duplicate_files:
                file_size = file_path.stat().st_size
                report_lines.append(f"  - {file_path} ({file_size / (1024**2):.1f} MB)")
            
            report_lines.append("")
        
        report = "\n".join(report_lines)
        
        if output_file:
            output_file.write_text(report)
            self.logger.info(f"Report saved to: {output_file}")
        
        return report
    
    def save_hash_database(self, output_file: Path) -> None:
        """Save the hash database to a JSON file for later use."""
        hash_db = {
            "metadata": {
                "algorithm": self.hash_algorithm,
                "generated": time.strftime('%Y-%m-%d %H:%M:%S'),
                "total_files": self.processed_files
            },
            "hashes": {
                hash_val: [str(path) for path in paths]
                for hash_val, paths in self.file_hashes.items()
            }
        }
        
        with open(output_file, 'w') as f:
            json.dump(hash_db, f, indent=2)
        
        self.logger.info(f"Hash database saved to: {output_file}")
    
    def load_hash_database(self, input_file: Path) -> None:
        """Load a previously saved hash database."""
        with open(input_file, 'r') as f:
            hash_db = json.load(f)
        
        self.hash_algorithm = hash_db["metadata"]["algorithm"]
        self.processed_files = hash_db["metadata"]["total_files"]
        
        self.file_hashes = defaultdict(list)
        for hash_val, path_strings in hash_db["hashes"].items():
            self.file_hashes[hash_val] = [Path(p) for p in path_strings]
        
        self.logger.info(f"Loaded hash database from: {input_file}")
        self.logger.info(f"Loaded {len(self.file_hashes)} unique hashes for {self.processed_files} files")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Find and remove duplicate files based on content hash"
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="Directory to scan for duplicates"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually removing files"
    )
    parser.add_argument(
        "--hash-algorithm",
        choices=["sha256", "md5", "sha1"],
        default="sha256",
        help="Hash algorithm to use (default: sha256)"
    )
    parser.add_argument(
        "--include",
        nargs="+",
        help="File patterns to include (e.g., *.jpg *.png)"
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        help="File patterns to exclude"
    )
    parser.add_argument(
        "--keep-strategy",
        choices=["shortest_path", "oldest", "newest", "largest_name", "first_alphabetical"],
        default="shortest_path",
        help="Strategy for choosing which duplicate to keep (default: shortest_path)"
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Don't scan subdirectories recursively"
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Generate detailed report and save to file"
    )
    parser.add_argument(
        "--save-hashes",
        type=Path,
        help="Save hash database to JSON file"
    )
    parser.add_argument(
        "--load-hashes",
        type=Path,
        help="Load hash database from JSON file (skip scanning)"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.load_hashes and (not args.directory.exists() or not args.directory.is_dir()):
        print(f"Error: Directory does not exist or is not a directory: {args.directory}")
        return 1
    
    # Create deduplicator
    deduplicator = FileDuplicateRemover(
        dry_run=args.dry_run,
        hash_algorithm=args.hash_algorithm
    )
    
    try:
        # Load existing hash database or scan directory
        if args.load_hashes:
            deduplicator.load_hash_database(args.load_hashes)
        else:
            deduplicator.scan_directory(
                args.directory,
                include_patterns=args.include,
                exclude_patterns=args.exclude,
                recursive=not args.no_recursive
            )
            
            # Save hash database if requested
            if args.save_hashes:
                deduplicator.save_hash_database(args.save_hashes)
        
        # Find duplicates
        duplicates = deduplicator.find_duplicates()
        
        if not duplicates:
            print("No duplicates found!")
            return 0
        
        # Generate report if requested
        if args.report:
            deduplicator.generate_report(duplicates, args.report)
        
        # Remove duplicates
        deduplicator.remove_duplicates(duplicates, args.keep_strategy)
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
