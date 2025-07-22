#!/usr/bin/env python3
"""
Tests for the deduplicate module.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import json
import hashlib
import time
import os

from data_recovery.deduplicate import FileDuplicateRemover


class TestFileDuplicateRemover(unittest.TestCase):
    """Test cases for FileDuplicateRemover class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.deduplicator = FileDuplicateRemover(dry_run=False)
        
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)
    
    def create_test_file(self, filename: str, content: bytes = b"test content") -> Path:
        """Create a test file with specified content."""
        file_path = self.test_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        return file_path
    
    def test_init(self):
        """Test FileDuplicateRemover initialization."""
        dedup = FileDuplicateRemover(dry_run=True, hash_algorithm="md5")
        self.assertTrue(dedup.dry_run)
        self.assertEqual(dedup.hash_algorithm, "md5")
        self.assertEqual(dedup.processed_files, 0)
        self.assertEqual(dedup.duplicates_found, 0)
    
    def test_calculate_file_hash(self):
        """Test file hash calculation."""
        content = b"Hello, World!"
        file_path = self.create_test_file("test.txt", content)
        
        # Calculate expected hash
        expected_hash = hashlib.sha256(content).hexdigest()
        
        # Test our implementation
        calculated_hash = self.deduplicator.calculate_file_hash(file_path)
        self.assertEqual(calculated_hash, expected_hash)
    
    def test_calculate_file_hash_different_algorithms(self):
        """Test hash calculation with different algorithms."""
        content = b"Test content for hashing"
        file_path = self.create_test_file("test.txt", content)
        
        # Test different algorithms
        for algorithm in ["sha256", "md5", "sha1"]:
            dedup = FileDuplicateRemover(hash_algorithm=algorithm)
            calculated_hash = dedup.calculate_file_hash(file_path)
            expected_hash = hashlib.new(algorithm, content).hexdigest()
            self.assertEqual(calculated_hash, expected_hash)
    
    def test_calculate_file_hash_nonexistent(self):
        """Test hash calculation for nonexistent file."""
        nonexistent = self.test_dir / "nonexistent.txt"
        result = self.deduplicator.calculate_file_hash(nonexistent)
        self.assertIsNone(result)
    
    def test_scan_directory_basic(self):
        """Test basic directory scanning."""
        # Create test files
        self.create_test_file("file1.txt", b"content1")
        self.create_test_file("file2.jpg", b"content2")
        self.create_test_file("subdir/file3.pdf", b"content3")
        
        self.deduplicator.scan_directory(self.test_dir)
        
        self.assertEqual(self.deduplicator.processed_files, 3)
        self.assertEqual(len(self.deduplicator.file_hashes), 3)  # All unique
    
    def test_scan_directory_with_duplicates(self):
        """Test scanning directory with duplicate files."""
        # Create files with same content
        same_content = b"duplicate content"
        self.create_test_file("file1.txt", same_content)
        self.create_test_file("file2.txt", same_content)
        self.create_test_file("file3.txt", b"unique content")
        
        self.deduplicator.scan_directory(self.test_dir)
        
        self.assertEqual(self.deduplicator.processed_files, 3)
        self.assertEqual(len(self.deduplicator.file_hashes), 2)  # 2 unique hashes
        
        # Find the hash for duplicate files
        duplicate_hash = None
        for hash_val, paths in self.deduplicator.file_hashes.items():
            if len(paths) == 2:
                duplicate_hash = hash_val
                break
        
        self.assertIsNotNone(duplicate_hash)
    
    def test_scan_directory_include_patterns(self):
        """Test scanning with include patterns."""
        self.create_test_file("photo1.jpg", b"photo1")
        self.create_test_file("photo2.png", b"photo2")
        self.create_test_file("document.pdf", b"document")
        self.create_test_file("text.txt", b"text")
        
        self.deduplicator.scan_directory(self.test_dir, include_patterns=["*.jpg", "*.png"])
        
        self.assertEqual(self.deduplicator.processed_files, 2)  # Only jpg and png
    
    def test_scan_directory_exclude_patterns(self):
        """Test scanning with exclude patterns."""
        self.create_test_file("photo1.jpg", b"photo1")
        self.create_test_file("photo2.png", b"photo2")
        self.create_test_file("document.pdf", b"document")
        self.create_test_file("backup.bak", b"backup")
        
        self.deduplicator.scan_directory(self.test_dir, exclude_patterns=["*.bak", "*.tmp"])
        
        self.assertEqual(self.deduplicator.processed_files, 3)  # Excludes .bak file
    
    def test_scan_directory_non_recursive(self):
        """Test non-recursive directory scanning."""
        self.create_test_file("file1.txt", b"content1")
        self.create_test_file("subdir/file2.txt", b"content2")
        
        self.deduplicator.scan_directory(self.test_dir, recursive=False)
        
        self.assertEqual(self.deduplicator.processed_files, 1)  # Only top-level file
    
    def test_find_duplicates(self):
        """Test finding duplicates."""
        # Create duplicate files
        same_content = b"duplicate content"
        self.create_test_file("dup1.txt", same_content)
        self.create_test_file("dup2.txt", same_content)
        self.create_test_file("dup3.txt", same_content)
        self.create_test_file("unique.txt", b"unique content")
        
        self.deduplicator.scan_directory(self.test_dir)
        duplicates = self.deduplicator.find_duplicates()
        
        self.assertEqual(len(duplicates), 1)  # One set of duplicates
        duplicate_set = list(duplicates.values())[0]
        self.assertEqual(len(duplicate_set), 3)  # 3 duplicate files
        self.assertEqual(self.deduplicator.duplicates_found, 2)  # 2 files to remove
    
    def test_choose_file_to_keep_shortest_path(self):
        """Test choosing file to keep with shortest path strategy."""
        files = [
            self.test_dir / "very/long/path/to/file.txt",
            self.test_dir / "short/file.txt",
            self.test_dir / "file.txt"
        ]
        
        # Create the files
        for file_path in files:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.touch()
        
        chosen = self.deduplicator.choose_file_to_keep(files, "shortest_path")
        self.assertEqual(chosen, self.test_dir / "file.txt")
    
    def test_choose_file_to_keep_oldest(self):
        """Test choosing file to keep with oldest strategy."""
        files = []
        
        # Create files with different modification times
        for i, name in enumerate(["old.txt", "newer.txt", "newest.txt"]):
            file_path = self.create_test_file(name, b"content")
            # Set different modification times using os.utime
            timestamp = time.time() - (100 - i * 10)  # old.txt will be oldest
            os.utime(file_path, (timestamp, timestamp))
            files.append(file_path)
        
        chosen = self.deduplicator.choose_file_to_keep(files, "oldest")
        self.assertEqual(chosen.name, "old.txt")
    
    def test_choose_file_to_keep_newest(self):
        """Test choosing file to keep with newest strategy."""
        files = []
        
        # Create files with different modification times
        for i, name in enumerate(["old.txt", "newer.txt", "newest.txt"]):
            file_path = self.create_test_file(name, b"content")
            # Set different modification times using os.utime
            timestamp = time.time() - (100 - i * 10)  # newest.txt will be newest
            os.utime(file_path, (timestamp, timestamp))
            files.append(file_path)
        
        chosen = self.deduplicator.choose_file_to_keep(files, "newest")
        self.assertEqual(chosen.name, "newest.txt")
    
    def test_choose_file_to_keep_alphabetical(self):
        """Test choosing file to keep with alphabetical strategy."""
        files = [
            self.create_test_file("zebra.txt", b"content"),
            self.create_test_file("apple.txt", b"content"),
            self.create_test_file("banana.txt", b"content")
        ]
        
        chosen = self.deduplicator.choose_file_to_keep(files, "first_alphabetical")
        self.assertEqual(chosen.name, "apple.txt")
    
    def test_remove_duplicates_dry_run(self):
        """Test removing duplicates in dry run mode."""
        dry_dedup = FileDuplicateRemover(dry_run=True)
        
        # Create duplicate files
        same_content = b"duplicate content"
        file1 = self.create_test_file("dup1.txt", same_content)
        file2 = self.create_test_file("dup2.txt", same_content)
        
        dry_dedup.scan_directory(self.test_dir)
        duplicates = dry_dedup.find_duplicates()
        dry_dedup.remove_duplicates(duplicates)
        
        # Files should still exist in dry run
        self.assertTrue(file1.exists())
        self.assertTrue(file2.exists())
        self.assertGreater(dry_dedup.space_saved, 0)
    
    def test_remove_duplicates_actual(self):
        """Test actually removing duplicates."""
        # Create duplicate files
        same_content = b"duplicate content"
        file1 = self.create_test_file("keep.txt", same_content)
        file2 = self.create_test_file("subdir/remove.txt", same_content)
        
        self.deduplicator.scan_directory(self.test_dir)
        duplicates = self.deduplicator.find_duplicates()
        self.deduplicator.remove_duplicates(duplicates, "shortest_path")
        
        # Shorter path should be kept, longer path removed
        self.assertTrue(file1.exists())
        self.assertFalse(file2.exists())
    
    def test_remove_duplicates_error_handling(self):
        """Test error handling during file removal."""
        # Create duplicate files
        same_content = b"duplicate content"
        file1 = self.create_test_file("keep.txt", same_content)
        file2 = self.create_test_file("remove.txt", same_content)
        
        self.deduplicator.scan_directory(self.test_dir)
        duplicates = self.deduplicator.find_duplicates()
        
        # Mock file removal to raise an exception
        with patch('pathlib.Path.unlink') as mock_unlink:
            mock_unlink.side_effect = OSError("Permission denied")
            
            # Should not raise exception, just log error
            self.deduplicator.remove_duplicates(duplicates)
            
            # Verify unlink was attempted
            mock_unlink.assert_called()
    
    def test_generate_report(self):
        """Test generating duplicate report."""
        # Create duplicate files
        same_content = b"duplicate content"
        self.create_test_file("dup1.txt", same_content)
        self.create_test_file("dup2.txt", same_content)
        
        self.deduplicator.scan_directory(self.test_dir)
        duplicates = self.deduplicator.find_duplicates()
        
        report = self.deduplicator.generate_report(duplicates)
        
        self.assertIn("DUPLICATE FILES REPORT", report)
        self.assertIn("Total files scanned: 2", report)
        self.assertIn("Duplicate sets found: 1", report)
        self.assertIn("dup1.txt", report)
        self.assertIn("dup2.txt", report)
    
    def test_save_and_load_hash_database(self):
        """Test saving and loading hash database."""
        # Create test files
        self.create_test_file("file1.txt", b"content1")
        self.create_test_file("file2.txt", b"content2")
        
        # Scan and save
        self.deduplicator.scan_directory(self.test_dir)
        db_file = self.test_dir / "hashes.json"
        self.deduplicator.save_hash_database(db_file)
        
        # Verify file was created
        self.assertTrue(db_file.exists())
        
        # Load into new deduplicator
        new_dedup = FileDuplicateRemover()
        new_dedup.load_hash_database(db_file)
        
        self.assertEqual(new_dedup.processed_files, self.deduplicator.processed_files)
        self.assertEqual(len(new_dedup.file_hashes), len(self.deduplicator.file_hashes))
    
    def test_large_file_handling(self):
        """Test handling of larger files."""
        # Create a larger file (1MB)
        large_content = b"x" * (1024 * 1024)
        file_path = self.create_test_file("large.txt", large_content)
        
        file_hash = self.deduplicator.calculate_file_hash(file_path)
        expected_hash = hashlib.sha256(large_content).hexdigest()
        
        self.assertEqual(file_hash, expected_hash)
    
    def test_filter_files_case_insensitive(self):
        """Test that file filtering is case insensitive."""
        files = [
            self.create_test_file("Photo.JPG", b"photo1"),
            self.create_test_file("image.PNG", b"photo2"),
            self.create_test_file("doc.PDF", b"document")
        ]
        
        filtered = self.deduplicator._filter_files(files, include_patterns=["*.jpg", "*.png"])
        self.assertEqual(len(filtered), 2)  # Should match JPG and PNG despite case


class TestFileDuplicateRemoverCLI(unittest.TestCase):
    """Test cases for CLI functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)
    
    def create_test_file(self, filename: str, content: bytes = b"test content") -> Path:
        """Create a test file with specified content."""
        file_path = self.test_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        return file_path
    
    @patch('argparse.ArgumentParser.parse_args')
    def test_cli_basic_usage(self, mock_parse_args):
        """Test basic CLI usage."""
        from data_recovery.deduplicate import main
        
        # Create test files
        same_content = b"duplicate content"
        self.create_test_file("dup1.txt", same_content)
        self.create_test_file("dup2.txt", same_content)
        
        # Mock arguments
        mock_args = MagicMock()
        mock_args.directory = self.test_dir
        mock_args.dry_run = True
        mock_args.hash_algorithm = "sha256"
        mock_args.include = None
        mock_args.exclude = None
        mock_args.keep_strategy = "shortest_path"
        mock_args.no_recursive = False
        mock_args.report = None
        mock_args.save_hashes = None
        mock_args.load_hashes = None
        mock_parse_args.return_value = mock_args
        
        result = main()
        self.assertEqual(result, 0)
    
    @patch('argparse.ArgumentParser.parse_args')
    def test_cli_with_report(self, mock_parse_args):
        """Test CLI with report generation."""
        from data_recovery.deduplicate import main
        
        # Create test files
        same_content = b"duplicate content"
        self.create_test_file("dup1.txt", same_content)
        self.create_test_file("dup2.txt", same_content)
        
        report_file = self.test_dir / "report.txt"
        
        # Mock arguments
        mock_args = MagicMock()
        mock_args.directory = self.test_dir
        mock_args.dry_run = True
        mock_args.hash_algorithm = "sha256"
        mock_args.include = None
        mock_args.exclude = None
        mock_args.keep_strategy = "shortest_path"
        mock_args.no_recursive = False
        mock_args.report = report_file
        mock_args.save_hashes = None
        mock_args.load_hashes = None
        mock_parse_args.return_value = mock_args
        
        result = main()
        self.assertEqual(result, 0)
        self.assertTrue(report_file.exists())


if __name__ == "__main__":
    unittest.main()
