#!/usr/bin/env python3
"""
Tests for the photo organizer script.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import os
import sys
from datetime import datetime

# Add the parent directory to the Python path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_recovery.sort_photos import PhotoOrganizer


class TestPhotoOrganizer(unittest.TestCase):
    """Test cases for PhotoOrganizer class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.source_dir = self.temp_dir / "source"
        self.target_dir = self.temp_dir / "target"
        self.source_dir.mkdir()
        self.target_dir.mkdir()

        self.organizer = PhotoOrganizer(
            str(self.source_dir),
            str(self.target_dir),
            dry_run=True
        )

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def create_test_file(self, filename: str, content: bytes = b"fake image data") -> Path:
        """Create a test file with given content."""
        file_path = self.source_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        return file_path

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        test_cases = [
            ("Normal Photo.jpg", "Normal Photo.jpg"),
            ("Photo<with>bad:chars", "Photo_with_bad_chars"),
            ('Photo"with|more?bad*chars', "Photo_with_more_bad_chars"),
            ("   .Leading dots and spaces   ", "Leading dots and spaces"),
            ("", "Unknown"),
            ("A" * 250, "A" * 200),  # Length limit
        ]

        for input_name, expected in test_cases:
            with self.subTest(input_name=input_name):
                result = self.organizer.sanitize_filename(input_name)
                self.assertEqual(result, expected)

    def test_supported_formats(self):
        """Test that supported formats are correctly identified."""
        supported_files = [
            "photo.jpg", "photo.jpeg", "photo.JPG", "photo.JPEG",
            "photo.png", "photo.tiff", "photo.tif", "photo.bmp",
            "photo.gif", "photo.webp", "photo.heic", "photo.heif",
            "photo.raw", "photo.cr2", "photo.nef", "photo.arw", "photo.dng"
        ]
        
        unsupported_files = [
            "document.txt", "video.mp4", "audio.mp3", "archive.zip"
        ]

        # Create test files
        for filename in supported_files + unsupported_files:
            self.create_test_file(filename)

        photo_files = self.organizer.find_photo_files()
        found_names = [f.name for f in photo_files]

        # Check all supported files are found
        for filename in supported_files:
            self.assertIn(filename, found_names)

        # Check unsupported files are not found
        for filename in unsupported_files:
            self.assertNotIn(filename, found_names)

    @patch('data_recovery.sort_photos.Image')
    def test_extract_exif_date_success(self, mock_image):
        """Test successful EXIF date extraction."""
        # Mock the PIL Image and EXIF data
        mock_img = MagicMock()
        mock_image.open.return_value.__enter__.return_value = mock_img
        
        # Mock EXIF data with DateTimeOriginal
        mock_exif = {
            36867: "2023:12:25 14:30:22"  # DateTimeOriginal tag
        }
        mock_img._getexif.return_value = mock_exif

        # Mock TAGS to return the correct tag name
        with patch('data_recovery.sort_photos.TAGS', {36867: 'DateTimeOriginal'}):
            test_file = self.create_test_file("test.jpg")
            result = self.organizer.extract_exif_date(test_file)
            expected = (datetime(2023, 12, 25, 14, 30, 22), False)
            self.assertEqual(result, expected)

    @patch('data_recovery.sort_photos.Image')
    def test_extract_exif_date_no_exif(self, mock_image):
        """Test handling of photos without EXIF data."""
        mock_img = MagicMock()
        mock_image.open.return_value.__enter__.return_value = mock_img
        mock_img._getexif.return_value = None

        test_file = self.create_test_file("test.jpg")
        result = self.organizer.extract_exif_date(test_file)
        self.assertEqual(result, (None, False))

    @patch('data_recovery.sort_photos.Image')
    def test_extract_exif_date_invalid_format(self, mock_image):
        """Test handling of invalid date formats in EXIF."""
        mock_img = MagicMock()
        mock_image.open.return_value.__enter__.return_value = mock_img
        
        # Mock EXIF with invalid date format
        mock_exif = {
            36867: "invalid date format"
        }
        mock_img._getexif.return_value = mock_exif

        with patch('data_recovery.sort_photos.TAGS', {36867: 'DateTimeOriginal'}):
            test_file = self.create_test_file("test.jpg")
            result = self.organizer.extract_exif_date(test_file)
            self.assertEqual(result, (None, False))

    @patch('data_recovery.sort_photos.Image')
    def test_extract_exif_date_alternative_format(self, mock_image):
        """Test extraction with alternative date format."""
        mock_img = MagicMock()
        mock_image.open.return_value.__enter__.return_value = mock_img
        
        # Mock EXIF data with alternative format
        mock_exif = {
            306: "2023-12-25 14:30:22"  # DateTime tag with dash format
        }
        mock_img._getexif.return_value = mock_exif

        with patch('data_recovery.sort_photos.TAGS', {306: 'DateTime'}):
            test_file = self.create_test_file("test.jpg")
            result = self.organizer.extract_exif_date(test_file)
            expected = (datetime(2023, 12, 25, 14, 30, 22), False)
            self.assertEqual(result, expected)

    @patch('data_recovery.sort_photos.Image')
    def test_extract_exif_date_exception_handling(self, mock_image):
        """Test exception handling during EXIF extraction."""
        mock_image.open.side_effect = Exception("Corrupted file")

        test_file = self.create_test_file("corrupted.jpg")
        result = self.organizer.extract_exif_date(test_file)
        self.assertEqual(result, (None, True))

    def test_generate_target_path(self):
        """Test target path generation."""
        test_file = self.source_dir / "vacation_photo.jpg"
        date_taken = datetime(2023, 12, 25, 14, 30, 22)
        
        result = self.organizer.generate_target_path(test_file, date_taken)
        
        expected_path = self.target_dir / "2023" / "12-December" / "20231225_143022_vacation_photo.jpg"
        self.assertEqual(result, expected_path)

    def test_generate_target_path_with_sanitization(self):
        """Test target path generation with filename sanitization."""
        test_file = self.source_dir / "bad<file>name.jpg"
        date_taken = datetime(2023, 1, 15, 9, 45, 30)
        
        result = self.organizer.generate_target_path(test_file, date_taken)
        
        expected_path = self.target_dir / "2023" / "01-January" / "20230115_094530_bad_file_name.jpg"
        self.assertEqual(result, expected_path)

    def test_move_file_dry_run(self):
        """Test file moving in dry run mode."""
        source_file = self.create_test_file("test.jpg")
        target_file = self.target_dir / "2023" / "01-January" / "test.jpg"
        
        result = self.organizer.move_file(source_file, target_file)
        
        self.assertTrue(result)
        self.assertTrue(source_file.exists())  # File should still exist in dry run
        self.assertFalse(target_file.exists())  # Target should not be created

    def test_move_file_actual_move(self):
        """Test actual file moving (not dry run)."""
        # Create organizer without dry run
        organizer = PhotoOrganizer(
            str(self.source_dir),
            str(self.target_dir),
            dry_run=False
        )
        
        source_file = self.create_test_file("test.jpg")
        target_file = self.target_dir / "2023" / "01-January" / "test.jpg"
        
        result = organizer.move_file(source_file, target_file)
        
        self.assertTrue(result)
        self.assertFalse(source_file.exists())  # Source should be moved
        self.assertTrue(target_file.exists())   # Target should exist

    def test_move_file_duplicate_handling(self):
        """Test handling of duplicate filenames."""
        # Create organizer without dry run
        organizer = PhotoOrganizer(
            str(self.source_dir),
            str(self.target_dir),
            dry_run=False
        )
        
        # Create target directory and existing file
        target_dir = self.target_dir / "2023" / "01-January"
        target_dir.mkdir(parents=True)
        existing_file = target_dir / "test.jpg"
        existing_file.write_bytes(b"existing content")
        
        source_file = self.create_test_file("test.jpg", b"new content")
        target_file = target_dir / "test.jpg"
        
        result = organizer.move_file(source_file, target_file)
        
        self.assertTrue(result)
        self.assertFalse(source_file.exists())  # Source should be moved
        self.assertTrue(existing_file.exists())  # Original should remain
        self.assertTrue((target_dir / "test_1.jpg").exists())  # Renamed version should exist

    @patch('data_recovery.sort_photos.Image')
    def test_organize_photos_complete_workflow(self, mock_image):
        """Test the complete photo organization workflow."""
        # Mock successful EXIF extraction
        mock_img = MagicMock()
        mock_image.open.return_value.__enter__.return_value = mock_img
        mock_exif = {36867: "2023:12:25 14:30:22"}
        mock_img._getexif.return_value = mock_exif

        with patch('data_recovery.sort_photos.TAGS', {36867: 'DateTimeOriginal'}):
            # Create test files
            self.create_test_file("photo1.jpg")
            self.create_test_file("photo2.jpeg")
            self.create_test_file("document.txt")  # Should be ignored
            
            stats = self.organizer.organize_photos()
            
            self.assertEqual(stats['processed'], 2)  # Only photo files processed
            self.assertEqual(stats['moved'], 2)      # Both photos should be "moved" (dry run)
            self.assertEqual(stats['skipped'], 0)
            self.assertEqual(stats['errors'], 0)

    @patch('data_recovery.sort_photos.Image')
    def test_organize_photos_with_skipped_files(self, mock_image):
        """Test workflow with photos that have no EXIF data."""
        # Mock no EXIF data
        mock_img = MagicMock()
        mock_image.open.return_value.__enter__.return_value = mock_img
        mock_img._getexif.return_value = None

        # Create test files
        self.create_test_file("photo_no_exif.jpg")
        
        stats = self.organizer.organize_photos()
        
        self.assertEqual(stats['processed'], 1)
        self.assertEqual(stats['moved'], 0)
        self.assertEqual(stats['skipped'], 1)
        self.assertEqual(stats['errors'], 0)

    @patch('data_recovery.sort_photos.Image')
    def test_organize_photos_with_errors(self, mock_image):
        """Test workflow with file processing errors."""
        # Mock exception during processing
        mock_image.open.side_effect = Exception("File error")

        # Create test files
        self.create_test_file("corrupted.jpg")
        
        stats = self.organizer.organize_photos()
        
        self.assertEqual(stats['processed'], 1)
        self.assertEqual(stats['moved'], 0)
        self.assertEqual(stats['skipped'], 0)
        self.assertEqual(stats['errors'], 1)

    def test_find_photo_files_recursive(self):
        """Test recursive finding of photo files."""
        # Create nested directory structure
        nested_dir = self.source_dir / "subfolder" / "deep"
        nested_dir.mkdir(parents=True)
        
        # Create files at different levels
        self.create_test_file("root.jpg")
        self.create_test_file("subfolder/sub.jpeg")
        self.create_test_file("subfolder/deep/deep.png")
        self.create_test_file("subfolder/document.txt")  # Not a photo
        
        photo_files = self.organizer.find_photo_files()
        photo_names = [f.name for f in photo_files]
        
        self.assertEqual(len(photo_files), 3)
        self.assertIn("root.jpg", photo_names)
        self.assertIn("sub.jpeg", photo_names)
        self.assertIn("deep.png", photo_names)
        self.assertNotIn("document.txt", photo_names)

    def test_initialization(self):
        """Test PhotoOrganizer initialization."""
        organizer = PhotoOrganizer("/source", "/target", dry_run=True)
        
        self.assertEqual(organizer.source_dir, Path("/source").resolve())
        self.assertEqual(organizer.target_dir, Path("/target").resolve())
        self.assertTrue(organizer.dry_run)
        self.assertEqual(organizer.stats['processed'], 0)
        self.assertEqual(organizer.stats['moved'], 0)
        self.assertEqual(organizer.stats['skipped'], 0)
        self.assertEqual(organizer.stats['errors'], 0)


if __name__ == '__main__':
    unittest.main()
