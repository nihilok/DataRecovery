#!/usr/bin/env python3
"""
Tests for the split_files module, including duplicate handling tests.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import os

from data_recovery.split_files import FileSplitter


class TestFileSplitter(unittest.TestCase):
    """Test cases for FileSplitter class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.source_dir = self.test_dir / "source"
        self.output_dir = self.test_dir / "output"
        self.source_dir.mkdir()
        self.output_dir.mkdir()

        # Create a splitter with small size for testing (10MB)
        self.splitter = FileSplitter(max_size_gb=0.01, dry_run=False)  # 10MB

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def create_test_file(self, filename: str, size_mb: float = 1.0) -> Path:
        """Create a test file with specified size."""
        file_path = self.source_dir / filename
        content = b"0" * int(size_mb * 1024 * 1024)  # Create file of specified size
        file_path.write_bytes(content)
        return file_path

    def test_init(self):
        """Test FileSplitter initialization."""
        splitter = FileSplitter(max_size_gb=2.0, dry_run=True)
        self.assertEqual(splitter.max_size_bytes, 2 * 1024 * 1024 * 1024)
        self.assertTrue(splitter.dry_run)

    def test_get_file_size(self):
        """Test getting file size."""
        file_path = self.create_test_file("test.txt", 5.0)  # 5MB
        size = self.splitter.get_file_size(file_path)
        expected_size = 5 * 1024 * 1024
        self.assertEqual(size, expected_size)

    def test_get_file_size_nonexistent(self):
        """Test getting size of nonexistent file."""
        nonexistent = self.source_dir / "nonexistent.txt"
        size = self.splitter.get_file_size(nonexistent)
        self.assertEqual(size, 0)

    def test_scan_directory(self):
        """Test scanning directory for files."""
        # Create test files
        self.create_test_file("file1.txt", 2.0)
        self.create_test_file("file2.jpg", 3.0)
        self.create_test_file("file3.pdf", 1.0)

        files = self.splitter.scan_directory(self.source_dir)

        # Should return 3 files, sorted by size (largest first)
        self.assertEqual(len(files), 3)
        # Check if sorted by size (descending)
        self.assertGreaterEqual(files[0][1], files[1][1])
        self.assertGreaterEqual(files[1][1], files[2][1])

    def test_scan_directory_nonexistent(self):
        """Test scanning nonexistent directory."""
        nonexistent_dir = self.test_dir / "nonexistent"
        with self.assertRaises(ValueError):
            self.splitter.scan_directory(nonexistent_dir)

    def test_calculate_splits_simple(self):
        """Test calculating splits for simple case."""
        # Create files that fit in one split
        file1 = self.create_test_file("file1.txt", 3.0)  # 3MB
        file2 = self.create_test_file("file2.txt", 4.0)  # 4MB
        file3 = self.create_test_file("file3.txt", 2.0)  # 2MB

        files = self.splitter.scan_directory(self.source_dir)
        splits = self.splitter.calculate_splits(files)

        # All files should fit in one split (total 9MB < 10MB limit)
        self.assertEqual(len(splits), 1)
        self.assertEqual(len(splits[0]), 3)

    def test_calculate_splits_multiple(self):
        """Test calculating splits that require multiple directories."""
        # Create files that require multiple splits
        file1 = self.create_test_file("file1.txt", 8.0)   # 8MB
        file2 = self.create_test_file("file2.txt", 6.0)   # 6MB
        file3 = self.create_test_file("file3.txt", 5.0)   # 5MB

        files = self.splitter.scan_directory(self.source_dir)
        splits = self.splitter.calculate_splits(files)

        # Should require 2 splits: first with 8MB file, second with 6MB+5MB=11MB > 10MB,
        # so actually 3 splits: [8MB], [6MB], [5MB]
        self.assertGreaterEqual(len(splits), 2)

    def test_calculate_splits_oversized_file(self):
        """Test handling of files larger than max size."""
        # Create a file larger than the limit
        large_file = self.create_test_file("large.txt", 15.0)  # 15MB > 10MB limit
        small_file = self.create_test_file("small.txt", 2.0)   # 2MB

        files = self.splitter.scan_directory(self.source_dir)
        splits = self.splitter.calculate_splits(files)

        # Large file should be in its own split
        self.assertGreaterEqual(len(splits), 2)
        # Find the split with the large file
        large_file_split = None
        for split in splits:
            if any(file_path.name == "large.txt" for file_path, _ in split):
                large_file_split = split
                break

        self.assertIsNotNone(large_file_split)
        self.assertEqual(len(large_file_split), 1)  # Large file should be alone

    def test_create_output_directories(self):
        """Test creating output directories."""
        directories = self.splitter.create_output_directories(self.output_dir, 3)

        self.assertEqual(len(directories), 3)
        for i, dir_path in enumerate(directories):
            expected_name = f"batch_{i+1:03d}"
            self.assertEqual(dir_path.name, expected_name)
            self.assertTrue(dir_path.exists())
            self.assertTrue(dir_path.is_dir())

    def test_dry_run_mode(self):
        """Test dry run mode doesn't create directories or move files."""
        dry_splitter = FileSplitter(max_size_gb=0.01, dry_run=True)

        # Create test files
        self.create_test_file("file1.txt", 2.0)
        self.create_test_file("file2.txt", 3.0)

        # Run split in dry run mode
        dry_splitter.split_directory(self.source_dir, self.output_dir)

        # Files should still be in source directory
        self.assertTrue((self.source_dir / "file1.txt").exists())
        self.assertTrue((self.source_dir / "file2.txt").exists())

        # No batch directories should be created
        batch_dirs = list(self.output_dir.glob("batch_*"))
        self.assertEqual(len(batch_dirs), 0)

    def test_duplicate_filename_handling(self):
        """Test handling of duplicate filenames."""
        # Create a file in source
        source_file = self.create_test_file("duplicate.txt", 2.0)

        # Create a file with same name in output directory
        batch_dir = self.output_dir / "batch_001"
        batch_dir.mkdir()
        existing_file = batch_dir / "duplicate.txt"
        existing_file.write_text("existing content")

        # Simulate moving the file (test the duplicate handling logic)
        files = [(source_file, 2 * 1024 * 1024)]  # 2MB
        splits = [files]
        output_dirs = [batch_dir]

        self.splitter.move_files(splits, output_dirs)

        # Original file should be renamed
        self.assertTrue((batch_dir / "duplicate_001.txt").exists())
        # Original duplicate should still exist
        self.assertTrue(existing_file.exists())

    def test_multiple_duplicate_handling(self):
        """Test handling of multiple files with same name."""
        # Create source file
        source_file = self.create_test_file("multi_dup.txt", 1.0)

        # Create output directory with existing files
        batch_dir = self.output_dir / "batch_001"
        batch_dir.mkdir()

        # Create multiple existing files with same base name
        (batch_dir / "multi_dup.txt").write_text("original")
        (batch_dir / "multi_dup_001.txt").write_text("first duplicate")
        (batch_dir / "multi_dup_002.txt").write_text("second duplicate")

        # Move the new file
        files = [(source_file, 1 * 1024 * 1024)]
        splits = [files]
        output_dirs = [batch_dir]

        self.splitter.move_files(splits, output_dirs)

        # New file should be renamed to _003
        self.assertTrue((batch_dir / "multi_dup_003.txt").exists())
        # All original files should still exist
        self.assertTrue((batch_dir / "multi_dup.txt").exists())
        self.assertTrue((batch_dir / "multi_dup_001.txt").exists())
        self.assertTrue((batch_dir / "multi_dup_002.txt").exists())

    def test_duplicate_with_different_extensions(self):
        """Test duplicate handling preserves file extensions."""
        # Create source files with different extensions
        source_jpg = self.create_test_file("image.jpg", 1.0)
        source_png = self.create_test_file("image.png", 1.0)

        # Create output directory with existing file
        batch_dir = self.output_dir / "batch_001"
        batch_dir.mkdir()
        (batch_dir / "image.jpg").write_bytes(b"existing jpg")

        # Move files
        files = [(source_jpg, 1024*1024), (source_png, 1024*1024)]
        splits = [files]
        output_dirs = [batch_dir]

        self.splitter.move_files(splits, output_dirs)

        # JPG should be renamed, PNG should keep original name
        self.assertTrue((batch_dir / "image_001.jpg").exists())
        self.assertTrue((batch_dir / "image.png").exists())
        self.assertTrue((batch_dir / "image.jpg").exists())  # Original

    def test_get_statistics(self):
        """Test getting directory statistics."""
        # Create test files of different types
        self.create_test_file("photo1.jpg", 2.0)
        self.create_test_file("photo2.jpg", 3.0)
        self.create_test_file("document.pdf", 1.5)
        self.create_test_file("text.txt", 0.5)

        stats = self.splitter.get_statistics(self.source_dir)

        self.assertEqual(stats["total_files"], 4)
        self.assertAlmostEqual(stats["total_size_gb"], 7.0 / 1024, places=3)  # 7MB in GB

        # Check file types
        expected_types = {".jpg": 2, ".pdf": 1, ".txt": 1}
        self.assertEqual(stats["file_types"], expected_types)

        # Should estimate at least 1 subdirectory
        self.assertGreaterEqual(stats["estimated_subdirs"], 1)

    def test_empty_directory_statistics(self):
        """Test statistics for empty directory."""
        stats = self.splitter.get_statistics(self.source_dir)

        self.assertEqual(stats["total_files"], 0)
        self.assertEqual(stats["total_size_gb"], 0)
        self.assertEqual(stats["file_types"], {})

    def test_integration_full_split(self):
        """Integration test for complete split operation."""
        # Create a set of files that will require multiple splits
        self.create_test_file("large1.jpg", 8.0)   # 8MB
        self.create_test_file("large2.jpg", 7.0)   # 7MB
        self.create_test_file("medium1.pdf", 4.0)  # 4MB
        self.create_test_file("medium2.pdf", 3.0)  # 3MB
        self.create_test_file("small1.txt", 1.0)   # 1MB
        self.create_test_file("small2.txt", 1.0)   # 1MB

        # Perform the split
        self.splitter.split_directory(self.source_dir, self.output_dir)

        # Verify source directory is empty (files moved)
        source_files = list(self.source_dir.glob("*"))
        self.assertEqual(len(source_files), 0)

        # Verify output directories were created
        batch_dirs = sorted(self.output_dir.glob("batch_*"))
        self.assertGreater(len(batch_dirs), 0)

        # Verify all files were moved
        total_files_moved = 0
        for batch_dir in batch_dirs:
            files_in_batch = list(batch_dir.glob("*"))
            total_files_moved += len(files_in_batch)

            # Verify batch size doesn't exceed limit (with small tolerance for rounding)
            batch_size = sum(f.stat().st_size for f in files_in_batch)
            self.assertLessEqual(batch_size, self.splitter.max_size_bytes * 1.1)  # 10% tolerance

        self.assertEqual(total_files_moved, 6)  # All 6 files should be moved

    def test_error_handling_move_files(self):
        """Test error handling during file moves."""
        # Create a source file
        source_file = self.create_test_file("test.txt", 1.0)

        # Create output directory
        batch_dir = self.output_dir / "batch_001"
        batch_dir.mkdir()

        # Mock shutil.move to raise an exception
        with patch('data_recovery.split_files.shutil.move') as mock_move:
            mock_move.side_effect = OSError("Permission denied")

            files = [(source_file, 1024*1024)]
            splits = [files]
            output_dirs = [batch_dir]

            # Should not raise exception, but log error
            self.splitter.move_files(splits, output_dirs)

            # Verify move was attempted
            mock_move.assert_called_once()


class TestFileSplitterCLI(unittest.TestCase):
    """Test cases for FileSplitter CLI functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.source_dir = self.test_dir / "source"
        self.output_dir = self.test_dir / "output"
        self.source_dir.mkdir()

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def create_test_file(self, filename: str, size_mb: float = 1.0) -> Path:
        """Create a test file with specified size."""
        file_path = self.source_dir / filename
        content = b"0" * int(size_mb * 1024 * 1024)
        file_path.write_bytes(content)
        return file_path

    @patch('argparse.ArgumentParser.parse_args')
    def test_cli_basic_usage(self, mock_parse_args):
        """Test basic CLI usage."""
        from data_recovery.split_files import main

        # Create test files
        self.create_test_file("test1.txt", 1.0)
        self.create_test_file("test2.txt", 1.0)

        # Mock parsed arguments
        mock_args = MagicMock()
        mock_args.source = self.source_dir
        mock_args.output = self.output_dir
        mock_args.max_size = 1.0
        mock_args.dry_run = True
        mock_args.stats = False
        mock_parse_args.return_value = mock_args

        # Should run without error
        result = main()
        self.assertEqual(result, 0)

    @patch('argparse.ArgumentParser.parse_args')
    def test_cli_stats_mode(self, mock_parse_args):
        """Test CLI stats mode."""
        from data_recovery.split_files import main

        # Create test files
        self.create_test_file("test1.jpg", 2.0)
        self.create_test_file("test2.pdf", 1.0)

        # Mock parsed arguments for stats
        mock_args = MagicMock()
        mock_args.source = self.source_dir
        mock_args.output = self.output_dir
        mock_args.max_size = 1.0
        mock_args.dry_run = False
        mock_args.stats = True
        mock_parse_args.return_value = mock_args

        # Capture output
        with patch('builtins.print') as mock_print:
            result = main()
            self.assertEqual(result, 0)

            # Verify stats were printed
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            stats_output = '\n'.join(print_calls)
            self.assertIn("Directory Statistics", stats_output)
            self.assertIn("Total files: 2", stats_output)
            self.assertIn(".jpg: 1", stats_output)
            self.assertIn(".pdf: 1", stats_output)

    @patch('argparse.ArgumentParser.parse_args')
    def test_cli_flatten_option(self, mock_parse_args):
        """Test CLI --flatten option."""
        from data_recovery.split_files import main
        # Create batch subdirectories and files
        batch1 = self.source_dir / "batch_001"
        batch2 = self.source_dir / "batch_002"
        batch1.mkdir()
        batch2.mkdir()
        (batch1 / "a.txt").write_text("A")
        (batch2 / "b.txt").write_text("B")
        # Mock parsed arguments
        mock_args = MagicMock()
        mock_args.source = self.source_dir
        mock_args.output = self.output_dir
        mock_args.max_size = 1.0
        mock_args.dry_run = False
        mock_args.stats = False
        mock_args.flatten = True
        mock_parse_args.return_value = mock_args
        # Should run without error
        result = main()
        self.assertEqual(result, 0)
        # Files should be in output_dir
        files = set(f.name for f in self.output_dir.iterdir())
        self.assertIn("a.txt", files)
        self.assertIn("b.txt", files)
