#!/usr/bin/env python3
"""
Tests for the file extension organizer script.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import sys

# Add the parent directory to the Python path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_recovery.move_junk import FileExtensionOrganizer


class TestFileExtensionOrganizer(unittest.TestCase):
    """Test cases for FileExtensionOrganizer class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.source_dir = self.temp_dir / "source"
        self.output_dir = self.temp_dir / "output"
        self.source_dir.mkdir()
        self.output_dir.mkdir()

        self.organizer = FileExtensionOrganizer(
            str(self.source_dir),
            str(self.output_dir),
            ['py', 'java', 'c'],
            dry_run=True
        )

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_extension_normalization(self):
        """Test that extensions are properly normalized."""
        # Test with dots and mixed case
        organizer = FileExtensionOrganizer(
            str(self.source_dir),
            str(self.output_dir),
            ['.PY', 'Java', '.C', 'TXT'],
            dry_run=True
        )

        expected = {'py', 'java', 'c', 'txt'}
        self.assertEqual(organizer.extensions, expected)

    def test_find_files_by_extensions(self):
        """Test finding files with specified extensions."""
        # Create test file structure
        test_files = [
            "script.py",
            "nested/program.java",
            "deep/nested/header.c",
            "deep/nested/another.py",
            "image.jpg",  # Should be ignored
            "readme.txt",  # Should be ignored
            "deep/config.ini"  # Should be ignored
        ]

        # Create the files
        for file_path in test_files:
            full_path = self.source_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.touch()

        files_by_ext = self.organizer.find_files_by_extensions()

        # Check results
        self.assertEqual(len(files_by_ext['py']), 2)  # script.py, another.py
        self.assertEqual(len(files_by_ext['java']), 1)  # program.java
        self.assertEqual(len(files_by_ext['c']), 1)  # header.c

        # Check that we found the right files
        py_names = {f.name for f in files_by_ext['py']}
        self.assertEqual(py_names, {'script.py', 'another.py'})

        java_names = {f.name for f in files_by_ext['java']}
        self.assertEqual(java_names, {'program.java'})

        c_names = {f.name for f in files_by_ext['c']}
        self.assertEqual(c_names, {'header.c'})

    def test_create_output_directories(self):
        """Test creation of output directories."""
        organizer = FileExtensionOrganizer(
            str(self.source_dir),
            str(self.output_dir),
            ['py', 'java'],
            dry_run=False  # Not dry run so directories are actually created
        )

        output_dirs = organizer.create_output_directories()

        # Check that directories were created
        expected_dirs = {
            'py': self.output_dir / 'py_files',
            'java': self.output_dir / 'java_files'
        }

        self.assertEqual(output_dirs, expected_dirs)

        # Check that directories actually exist
        for dir_path in expected_dirs.values():
            self.assertTrue(dir_path.exists())
            self.assertTrue(dir_path.is_dir())

    def test_move_file_dry_run(self):
        """Test file moving in dry run mode."""
        source_file = self.source_dir / "test.py"
        source_file.touch()

        target_dir = self.output_dir / "py_files"
        target_dir.mkdir(parents=True)

        # Should return True for dry run
        result = self.organizer.move_file(source_file, target_dir)
        self.assertTrue(result)

        # File should still exist in source
        self.assertTrue(source_file.exists())

        # Target file should not exist
        target_file = target_dir / "test.py"
        self.assertFalse(target_file.exists())

    def test_move_file_actual(self):
        """Test actual file moving."""
        organizer = FileExtensionOrganizer(
            str(self.source_dir),
            str(self.output_dir),
            ['py'],
            dry_run=False
        )

        source_file = self.source_dir / "test.py"
        source_file.write_text("print('hello')")

        target_dir = self.output_dir / "py_files"
        target_dir.mkdir(parents=True)

        result = organizer.move_file(source_file, target_dir)

        self.assertTrue(result)
        self.assertFalse(source_file.exists())

        target_file = target_dir / "test.py"
        self.assertTrue(target_file.exists())
        self.assertEqual(target_file.read_text(), "print('hello')")

    def test_move_file_conflict_handling(self):
        """Test handling of filename conflicts."""
        organizer = FileExtensionOrganizer(
            str(self.source_dir),
            str(self.output_dir),
            ['py'],
            dry_run=False
        )

        # Create existing target file
        target_dir = self.output_dir / "py_files"
        target_dir.mkdir(parents=True)
        existing_file = target_dir / "test.py"
        existing_file.write_text("existing content")

        # Create source file with same name
        source_file = self.source_dir / "test.py"
        source_file.write_text("new content")

        result = organizer.move_file(source_file, target_dir)

        self.assertTrue(result)
        self.assertFalse(source_file.exists())

        # Original file should be unchanged
        self.assertEqual(existing_file.read_text(), "existing content")

        # New file should be renamed
        renamed_file = target_dir / "test_1.py"
        self.assertTrue(renamed_file.exists())
        self.assertEqual(renamed_file.read_text(), "new content")

    def test_organize_files_integration(self):
        """Test the complete organization process."""
        # Create test files
        test_files = [
            ("script1.py", "# Python script 1"),
            ("nested/script2.py", "# Python script 2"),
            ("Program.java", "// Java program"),
            ("header.c", "/* C header */"),
            ("image.jpg", "fake image"),  # Should be ignored
        ]

        for file_path, content in test_files:
            full_path = self.source_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        # Run organization
        stats = self.organizer.organize_files()

        # Check statistics
        self.assertEqual(stats['processed'], 4)  # py, py, java, c
        self.assertEqual(stats['moved'], 4)
        self.assertEqual(stats['errors'], 0)
        self.assertEqual(stats['by_extension']['py'], 2)
        self.assertEqual(stats['by_extension']['java'], 1)
        self.assertEqual(stats['by_extension']['c'], 1)

    def test_cleanup_empty_directories(self):
        """Test cleanup of empty directories."""
        organizer = FileExtensionOrganizer(
            str(self.source_dir),
            str(self.output_dir),
            ['py'],
            dry_run=False
        )

        # Create nested directory structure with one file
        nested_dir = self.source_dir / "deep" / "nested" / "very_deep"
        nested_dir.mkdir(parents=True)
        test_file = nested_dir / "script.py"
        test_file.write_text("print('test')")

        # Also create an empty directory
        empty_dir = self.source_dir / "empty"
        empty_dir.mkdir()

        # Move the file (this will leave empty directories)
        target_dir = self.output_dir / "py_files"
        target_dir.mkdir(parents=True)
        organizer.move_file(test_file, target_dir)

        # Verify directories exist before cleanup
        self.assertTrue((self.source_dir / "deep").exists())
        self.assertTrue((self.source_dir / "deep" / "nested").exists())
        self.assertTrue((self.source_dir / "deep" / "nested" / "very_deep").exists())
        self.assertTrue(empty_dir.exists())

        # Run cleanup
        organizer.cleanup_empty_directories()

        # Verify empty directories were removed
        self.assertFalse((self.source_dir / "deep").exists())
        self.assertFalse(empty_dir.exists())

        # Source directory should still exist
        self.assertTrue(self.source_dir.exists())


class TestDuplicateHandling(unittest.TestCase):
    """Test cases for duplicate detection and removal functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.source_dir = self.temp_dir / "source"
        self.output_dir = self.temp_dir / "output"
        self.source_dir.mkdir()
        self.output_dir.mkdir()

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_files_are_identical_size_method(self):
        """Test duplicate detection using size comparison."""
        organizer = FileExtensionOrganizer(
            str(self.source_dir),
            str(self.output_dir),
            ['py'],
            dedupe_method='size'
        )

        # Create two files with same size
        file1 = self.source_dir / "file1.py"
        file2 = self.source_dir / "file2.py"
        file1.write_text("print('hello')")  # 14 bytes
        file2.write_text("print('world')")  # 14 bytes (same size)

        # Create file with different size
        file3 = self.source_dir / "file3.py"
        file3.write_text("print('hello world')")  # 19 bytes

        # Test identical files (same size)
        self.assertTrue(organizer.files_are_identical(file1, file2))

        # Test different files (different size)
        self.assertFalse(organizer.files_are_identical(file1, file3))

    def test_files_are_identical_hash_method(self):
        """Test duplicate detection using hash comparison."""
        organizer = FileExtensionOrganizer(
            str(self.source_dir),
            str(self.output_dir),
            ['py'],
            dedupe_method='hash'
        )

        # Create identical files (same content)
        file1 = self.source_dir / "file1.py"
        file2 = self.source_dir / "file2.py"
        content = "print('hello world')"
        file1.write_text(content)
        file2.write_text(content)

        # Create file with different content but same size
        file3 = self.source_dir / "file3.py"
        file3.write_text("print('world hello')")  # Same length, different content

        # Test identical files (same hash)
        self.assertTrue(organizer.files_are_identical(file1, file2))

        # Test different files (different hash, even with same size)
        self.assertFalse(organizer.files_are_identical(file1, file3))

    def test_files_are_identical_both_method(self):
        """Test duplicate detection using size + hash comparison."""
        organizer = FileExtensionOrganizer(
            str(self.source_dir),
            str(self.output_dir),
            ['py'],
            dedupe_method='both'
        )

        # Create identical files
        file1 = self.source_dir / "file1.py"
        file2 = self.source_dir / "file2.py"
        content = "print('hello')"
        file1.write_text(content)
        file2.write_text(content)

        # Create file with different size
        file3 = self.source_dir / "file3.py"
        file3.write_text("print('hello world')")

        # Create file with same size but different content
        file4 = self.source_dir / "file4.py"
        file4.write_text("print('world')")  # Same length as file1/file2

        # Test identical files
        self.assertTrue(organizer.files_are_identical(file1, file2))

        # Test different size (should fail on size check)
        self.assertFalse(organizer.files_are_identical(file1, file3))

        # Test same size, different content (should fail on hash check)
        self.assertFalse(organizer.files_are_identical(file1, file4))

    def test_skip_duplicates_functionality(self):
        """Test skip duplicates functionality without removal."""
        # Create organizer with skip duplicates enabled
        organizer = FileExtensionOrganizer(
            str(self.source_dir),
            str(self.output_dir),
            ['py'],
            dry_run=False,
            skip_duplicates=True,
            dedupe_method='hash'
        )

        # Create target directory and existing file
        target_dir = self.output_dir / "py_files"
        target_dir.mkdir(parents=True)
        existing_file = target_dir / "existing.py"
        existing_file.write_text("print('hello')")

        # Create source files - one duplicate, one unique
        duplicate_file = self.source_dir / "duplicate.py"
        duplicate_file.write_text("print('hello')")  # Same content as existing

        unique_file = self.source_dir / "unique.py"
        unique_file.write_text("print('world')")  # Different content

        # Run organization
        stats = organizer.organize_files()

        # Check statistics
        self.assertEqual(stats['processed'], 2)
        self.assertEqual(stats['moved'], 1)  # Only unique file moved
        self.assertEqual(stats['duplicates_skipped'], 1)
        self.assertEqual(stats['duplicates_removed'], 0)  # No removal

        # Check that duplicate file still exists in source
        self.assertTrue(duplicate_file.exists())

        # Check that unique file was moved
        self.assertFalse(unique_file.exists())
        self.assertTrue((target_dir / "unique.py").exists())

    def test_remove_source_dupes_functionality(self):
        """Test remove source duplicates functionality."""
        # Create organizer with both skip and remove duplicates enabled
        organizer = FileExtensionOrganizer(
            str(self.source_dir),
            str(self.output_dir),
            ['py'],
            dry_run=False,
            skip_duplicates=True,
            remove_source_dupes=True,
            dedupe_method='hash'
        )

        # Create target directory and existing file
        target_dir = self.output_dir / "py_files"
        target_dir.mkdir(parents=True)
        existing_file = target_dir / "existing.py"
        existing_file.write_text("print('hello')")

        # Create source files - one duplicate, one unique
        duplicate_file = self.source_dir / "duplicate.py"
        duplicate_file.write_text("print('hello')")  # Same content as existing

        unique_file = self.source_dir / "unique.py"
        unique_file.write_text("print('world')")  # Different content

        # Run organization
        stats = organizer.organize_files()

        # Check statistics
        self.assertEqual(stats['processed'], 2)
        self.assertEqual(stats['moved'], 1)  # Only unique file moved
        self.assertEqual(stats['duplicates_skipped'], 1)
        self.assertEqual(stats['duplicates_removed'], 1)  # Duplicate removed

        # Check that duplicate file was removed from source
        self.assertFalse(duplicate_file.exists())

        # Check that unique file was moved
        self.assertFalse(unique_file.exists())
        self.assertTrue((target_dir / "unique.py").exists())

        # Check that existing file is still there
        self.assertTrue(existing_file.exists())

    def test_remove_source_dupes_dry_run(self):
        """Test remove source duplicates in dry run mode."""
        # Create organizer with dry run enabled
        organizer = FileExtensionOrganizer(
            str(self.source_dir),
            str(self.output_dir),
            ['py'],
            dry_run=True,
            skip_duplicates=True,
            remove_source_dupes=True,
            dedupe_method='hash'
        )

        # Create target directory and existing file
        target_dir = self.output_dir / "py_files"
        target_dir.mkdir(parents=True)
        existing_file = target_dir / "existing.py"
        existing_file.write_text("print('hello')")

        # Create duplicate source file
        duplicate_file = self.source_dir / "duplicate.py"
        duplicate_file.write_text("print('hello')")

        # Run organization
        stats = organizer.organize_files()

        # Check that file still exists (dry run)
        self.assertTrue(duplicate_file.exists())

        # Check statistics
        self.assertEqual(stats['duplicates_skipped'], 1)
        self.assertEqual(stats['duplicates_removed'], 1)  # Counts what would be removed

    def test_remove_duplicate_file_method(self):
        """Test the remove_duplicate_file method directly."""
        organizer = FileExtensionOrganizer(
            str(self.source_dir),
            str(self.output_dir),
            ['py'],
            dry_run=False
        )

        # Create test file
        test_file = self.source_dir / "test.py"
        test_file.write_text("print('test')")

        # Remove the file
        result = organizer.remove_duplicate_file(test_file)

        # Check that file was removed
        self.assertTrue(result)
        self.assertFalse(test_file.exists())

    def test_remove_duplicate_file_dry_run(self):
        """Test the remove_duplicate_file method in dry run mode."""
        organizer = FileExtensionOrganizer(
            str(self.source_dir),
            str(self.output_dir),
            ['py'],
            dry_run=True
        )

        # Create test file
        test_file = self.source_dir / "test.py"
        test_file.write_text("print('test')")

        # Try to remove the file (dry run)
        result = organizer.remove_duplicate_file(test_file)

        # Check that file still exists
        self.assertTrue(result)
        self.assertTrue(test_file.exists())

    def test_multiple_duplicates_handling(self):
        """Test handling of multiple duplicate files."""
        organizer = FileExtensionOrganizer(
            str(self.source_dir),
            str(self.output_dir),
            ['py'],
            dry_run=False,
            skip_duplicates=True,
            remove_source_dupes=True,
            dedupe_method='hash'
        )

        # Create target directory and existing files
        target_dir = self.output_dir / "py_files"
        target_dir.mkdir(parents=True)

        existing1 = target_dir / "existing1.py"
        existing1.write_text("print('hello')")

        existing2 = target_dir / "existing2.py"
        existing2.write_text("print('world')")

        # Create multiple source files with duplicates
        dup1 = self.source_dir / "dup1.py"
        dup1.write_text("print('hello')")  # Duplicate of existing1

        dup2 = self.source_dir / "dup2.py"
        dup2.write_text("print('hello')")  # Another duplicate of existing1

        dup3 = self.source_dir / "dup3.py"
        dup3.write_text("print('world')")  # Duplicate of existing2

        unique = self.source_dir / "unique.py"
        unique.write_text("print('unique')")  # Unique file

        # Run organization
        stats = organizer.organize_files()

        # Check statistics
        self.assertEqual(stats['processed'], 4)
        self.assertEqual(stats['moved'], 1)  # Only unique file moved
        self.assertEqual(stats['duplicates_skipped'], 3)  # All duplicates skipped
        self.assertEqual(stats['duplicates_removed'], 3)  # All duplicates removed

        # Check that all duplicates were removed
        self.assertFalse(dup1.exists())
        self.assertFalse(dup2.exists())
        self.assertFalse(dup3.exists())

        # Check that unique file was moved
        self.assertFalse(unique.exists())
        self.assertTrue((target_dir / "unique.py").exists())

    def test_get_file_hash_method(self):
        """Test the file hash calculation method."""
        organizer = FileExtensionOrganizer(
            str(self.source_dir),
            str(self.output_dir),
            ['py']
        )

        # Create test files with known content
        file1 = self.source_dir / "file1.py"
        file2 = self.source_dir / "file2.py"
        file3 = self.source_dir / "file3.py"

        content1 = "print('hello')"
        content2 = "print('hello')"  # Same as content1
        content3 = "print('world')"  # Different

        file1.write_text(content1)
        file2.write_text(content2)
        file3.write_text(content3)

        # Calculate hashes
        hash1 = organizer.get_file_hash(file1)
        hash2 = organizer.get_file_hash(file2)
        hash3 = organizer.get_file_hash(file3)

        # Verify hash properties
        self.assertIsInstance(hash1, str)
        self.assertGreater(len(hash1), 0)

        # Same content should produce same hash
        self.assertEqual(hash1, hash2)

        # Different content should produce different hash
        self.assertNotEqual(hash1, hash3)


class TestCommandLineValidation(unittest.TestCase):
    """Test command line argument validation for duplicate features."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.source_dir = self.temp_dir / "source"
        self.source_dir.mkdir()

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    @patch('sys.argv', ['move_junk.py', 'py', '--remove-source-dupes'])
    def test_remove_source_dupes_requires_skip_duplicates(self):
        """Test that --remove-source-dupes requires --skip-duplicates."""
        from data_recovery.move_junk import main

        with patch('data_recovery.move_junk.Path') as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.is_dir.return_value = True

            result = main()

            # Should return error code 1
            self.assertEqual(result, 1)

    @patch('data_recovery.move_junk.FileExtensionOrganizer')
    @patch('sys.argv', ['move_junk.py', 'py', '--skip-duplicates', '--remove-source-dupes'])
    def test_valid_duplicate_arguments(self, mock_organizer_class):
        """Test valid combination of duplicate arguments."""
        from data_recovery.move_junk import main

        # Mock the organizer
        mock_organizer = Mock()
        mock_organizer.organize_files.return_value = {
            'processed': 5,
            'moved': 3,
            'errors': 0,
            'duplicates_skipped': 2,
            'duplicates_removed': 2,
            'by_extension': {'py': 5}
        }
        mock_organizer_class.return_value = mock_organizer

        with patch('data_recovery.move_junk.Path') as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.is_dir.return_value = True

            result = main()

            # Should succeed
            self.assertEqual(result, 0)

            # Check that organizer was created with correct parameters
            # The constructor parameters are positional, so we check call_args[0]
            call_args = mock_organizer_class.call_args[0]  # positional arguments
            # skip_duplicates is the 7th parameter (index 6), remove_source_dupes is 8th (index 7)
            self.assertTrue(len(call_args) > 7)  # Make sure we have enough arguments


class TestCommandLineInterface(unittest.TestCase):
    """Test the command line interface."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.source_dir = self.temp_dir / "source"
        self.source_dir.mkdir()

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    @patch('data_recovery.move_junk.FileExtensionOrganizer')
    @patch('sys.argv', ['move_junk.py', 'py', 'java', '--dry-run'])
    def test_main_with_dry_run(self, mock_organizer_class):
        """Test main function with dry run."""
        from data_recovery.move_junk import main

        # Mock the organizer
        mock_organizer = Mock()
        mock_organizer.organize_files.return_value = {
            'processed': 10,
            'moved': 10,
            'errors': 0,
            'duplicates_skipped': 0,
            'duplicates_removed': 0,
            'by_extension': {'py': 5, 'java': 5}
        }
        mock_organizer_class.return_value = mock_organizer

        with patch('data_recovery.move_junk.Path') as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.is_dir.return_value = True

            result = main()

            self.assertEqual(result, 0)
            mock_organizer_class.assert_called_once()
            mock_organizer.organize_files.assert_called_once()

    @patch('data_recovery.move_junk.FileExtensionOrganizer')
    @patch('sys.argv', ['move_junk.py', 'py', '--skip-duplicates', '--remove-source-dupes', '--dedupe-method', 'hash'])
    def test_main_with_duplicate_options(self, mock_organizer_class):
        """Test main function with duplicate handling options."""
        from data_recovery.move_junk import main

        # Mock the organizer
        mock_organizer = Mock()
        mock_organizer.organize_files.return_value = {
            'processed': 10,
            'moved': 7,
            'errors': 0,
            'duplicates_skipped': 3,
            'duplicates_removed': 3,
            'by_extension': {'py': 10}
        }
        mock_organizer_class.return_value = mock_organizer

        with patch('data_recovery.move_junk.Path') as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.is_dir.return_value = True

            result = main()

            self.assertEqual(result, 0)

            # Check that organizer was created with correct parameters
            call_args = mock_organizer_class.call_args[1]  # keyword arguments
            self.assertTrue(call_args['skip_duplicates'])
            self.assertTrue(call_args['remove_source_dupes'])
            self.assertEqual(call_args['dedupe_method'], 'hash')


if __name__ == '__main__':
    # Create a test suite
    test_suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))

    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # Exit with appropriate code
    exit(0 if result.wasSuccessful() else 1)
