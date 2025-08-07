#!/usr/bin/env python3
"""
Tests for the video organizer script.
"""

import unittest
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import os
import sys
from datetime import datetime
import subprocess

# Add the parent directory to the Python path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_recovery.sort_videos import VideoOrganizer


class TestVideoOrganizer(unittest.TestCase):
    """Test cases for VideoOrganizer class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.source_dir = self.temp_dir / "source"
        self.target_dir = self.temp_dir / "target"
        self.source_dir.mkdir()
        self.target_dir.mkdir()

        # Mock ffprobe check to avoid dependency
        with patch.object(VideoOrganizer, '_check_ffprobe', return_value=True):
            self.organizer = VideoOrganizer(
                str(self.source_dir),
                str(self.target_dir),
                dry_run=True
            )

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def create_test_file(self, filename: str, content: bytes = b"fake video data") -> Path:
        """Create a test file with given content."""
        file_path = self.source_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        return file_path

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        test_cases = [
            ("Normal Video.mp4", "Normal Video.mp4"),
            ("Video<with>bad:chars", "Video_with_bad_chars"),
            ('Video"with|more?bad*chars', "Video_with_more_bad_chars"),
            ("   .Leading dots and spaces   ", "Leading dots and spaces"),
            ("", "Unknown"),
            ("A" * 250, "A" * 200),  # Length limit
        ]

        for input_name, expected in test_cases:
            with self.subTest(input_name=input_name):
                result = self.organizer.sanitize_filename(input_name)
                self.assertEqual(result, expected)

    def test_supported_formats(self):
        """Test that supported video formats are correctly identified."""
        supported_files = [
            "video.mp4", "video.mov", "video.avi", "video.mkv",
            "video.wmv", "video.flv", "video.webm", "video.m4v",
            "video.3gp", "video.mpg", "video.mpeg", "video.m2v",
            "video.asf", "video.ts", "video.mts", "video.m2ts",
            "VIDEO.MP4", "VIDEO.MOV"  # Test case sensitivity
        ]
        
        unsupported_files = [
            "document.txt", "photo.jpg", "audio.mp3", "archive.zip"
        ]

        # Create test files
        for filename in supported_files + unsupported_files:
            self.create_test_file(filename)

        video_files = self.organizer.find_video_files()
        found_names = [f.name for f in video_files]

        # Check all supported files are found
        for filename in supported_files:
            self.assertIn(filename, found_names)

        # Check unsupported files are not found
        for filename in unsupported_files:
            self.assertNotIn(filename, found_names)

    @patch('subprocess.run')
    def test_check_ffprobe_available(self, mock_run):
        """Test ffprobe availability check."""
        mock_run.return_value = None
        result = self.organizer._check_ffprobe()
        self.assertTrue(result)
        mock_run.assert_called_once_with(['ffprobe', '-version'], 
                                       capture_output=True, check=True)

    @patch('subprocess.run')
    def test_check_ffprobe_not_available(self, mock_run):
        """Test ffprobe not available."""
        mock_run.side_effect = FileNotFoundError()
        result = self.organizer._check_ffprobe()
        self.assertFalse(result)

    def test_ffprobe_not_available_raises_error(self):
        """Test that missing ffprobe raises RuntimeError during initialization."""
        with patch.object(VideoOrganizer, '_check_ffprobe', return_value=False):
            with self.assertRaises(RuntimeError) as context:
                VideoOrganizer(str(self.source_dir), str(self.target_dir))
            self.assertIn("ffprobe not found", str(context.exception))

    @patch('subprocess.run')
    def test_extract_video_metadata_success(self, mock_run):
        """Test successful metadata extraction."""
        # Mock ffprobe output with creation time
        mock_metadata = {
            "format": {
                "tags": {
                    "creation_time": "2023-12-25T14:30:22.000000Z"
                }
            }
        }
        mock_run.return_value.stdout = json.dumps(mock_metadata)
        mock_run.return_value.returncode = 0

        test_file = self.create_test_file("test.mp4")
        result = self.organizer.extract_video_metadata(test_file)
        expected = (datetime(2023, 12, 25, 14, 30, 22), False)
        self.assertEqual(result, expected)

    @patch('subprocess.run')
    def test_extract_video_metadata_no_creation_time(self, mock_run):
        """Test metadata extraction when no creation time is found."""
        # Mock ffprobe output without creation time
        mock_metadata = {
            "format": {
                "tags": {}
            }
        }
        mock_run.return_value.stdout = json.dumps(mock_metadata)
        mock_run.return_value.returncode = 0

        test_file = self.create_test_file("test.mp4")
        result = self.organizer.extract_video_metadata(test_file)
        self.assertEqual(result, (None, False))

    @patch('subprocess.run')
    def test_extract_video_metadata_alternative_formats(self, mock_run):
        """Test metadata extraction with various date formats."""
        test_cases = [
            ("2023-12-25T14:30:22Z", datetime(2023, 12, 25, 14, 30, 22)),
            ("2023-12-25 14:30:22", datetime(2023, 12, 25, 14, 30, 22)),
            ("2023:12:25 14:30:22", datetime(2023, 12, 25, 14, 30, 22)),
            ("2023-12-25", datetime(2023, 12, 25, 0, 0, 0)),
        ]

        for date_str, expected_date in test_cases:
            with self.subTest(date_str=date_str):
                mock_metadata = {
                    "format": {
                        "tags": {
                            "creation_time": date_str
                        }
                    }
                }
                mock_run.return_value.stdout = json.dumps(mock_metadata)
                mock_run.return_value.returncode = 0

                test_file = self.create_test_file("test.mp4")
                result = self.organizer.extract_video_metadata(test_file)
                self.assertEqual(result, (expected_date, False))

    @patch('subprocess.run')
    def test_extract_video_metadata_alternative_fields(self, mock_run):
        """Test metadata extraction from alternative tag fields."""
        alternative_fields = [
            "date",
            "com.apple.quicktime.creationdate",
            "DATE_DIGITIZED",
            "DATE"
        ]

        for field in alternative_fields:
            with self.subTest(field=field):
                mock_metadata = {
                    "format": {
                        "tags": {
                            field: "2023-12-25T14:30:22.000000Z"
                        }
                    }
                }
                mock_run.return_value.stdout = json.dumps(mock_metadata)
                mock_run.return_value.returncode = 0

                test_file = self.create_test_file("test.mp4")
                result = self.organizer.extract_video_metadata(test_file)
                expected = (datetime(2023, 12, 25, 14, 30, 22), False)
                self.assertEqual(result, expected)

    @patch('subprocess.run')
    def test_extract_video_metadata_ffprobe_error(self, mock_run):
        """Test handling of ffprobe errors."""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'ffprobe')

        test_file = self.create_test_file("test.mp4")
        result = self.organizer.extract_video_metadata(test_file)
        self.assertEqual(result, (None, True))

    @patch('subprocess.run')
    def test_extract_video_metadata_invalid_json(self, mock_run):
        """Test handling of invalid JSON from ffprobe."""
        mock_run.return_value.stdout = "invalid json"
        mock_run.return_value.returncode = 0

        test_file = self.create_test_file("test.mp4")
        result = self.organizer.extract_video_metadata(test_file)
        self.assertEqual(result, (None, True))

    @patch('subprocess.run')
    def test_extract_video_metadata_ignores_zero_date(self, mock_run):
        """Test that zero dates are ignored."""
        mock_metadata = {
            "format": {
                "tags": {
                    "creation_time": "0000-00-00T00:00:00.000000Z"
                }
            }
        }
        mock_run.return_value.stdout = json.dumps(mock_metadata)
        mock_run.return_value.returncode = 0

        test_file = self.create_test_file("test.mp4")
        result = self.organizer.extract_video_metadata(test_file)
        self.assertEqual(result, (None, False))

    def test_get_file_modification_date(self):
        """Test getting file modification date."""
        test_file = self.create_test_file("test.mp4")
        result = self.organizer.get_file_modification_date(test_file)
        self.assertIsInstance(result, datetime)
        # Should be recent (within last minute)
        time_diff = datetime.now() - result
        self.assertLess(time_diff.total_seconds(), 60)

    def test_generate_target_path(self):
        """Test target path generation."""
        test_date = datetime(2023, 12, 25, 14, 30, 22)
        test_file = Path("test_video.mp4")
        
        result = self.organizer.generate_target_path(test_file, test_date)
        expected = self.target_dir / "2023" / "12-December" / "20231225_143022_test_video.mp4"
        self.assertEqual(result, expected)

    def test_generate_target_path_with_special_chars(self):
        """Test target path generation with special characters in filename."""
        test_date = datetime(2023, 1, 1, 9, 5, 30)
        test_file = Path("test<video>with:bad|chars.mp4")
        
        result = self.organizer.generate_target_path(test_file, test_date)
        expected = self.target_dir / "2023" / "01-January" / "20230101_090530_test_video_with_bad_chars.mp4"
        self.assertEqual(result, expected)

    def test_move_file_dry_run(self):
        """Test file moving in dry run mode."""
        test_file = self.create_test_file("test.mp4")
        target_path = self.target_dir / "moved.mp4"
        
        result = self.organizer.move_file(test_file, target_path)
        
        self.assertTrue(result)
        self.assertTrue(test_file.exists())  # Source should still exist in dry run
        self.assertFalse(target_path.exists())  # Target should not exist in dry run

    def test_move_file_actual_move(self):
        """Test actual file moving when not in dry run mode."""
        # Create organizer without dry run
        with patch.object(VideoOrganizer, '_check_ffprobe', return_value=True):
            organizer = VideoOrganizer(
                str(self.source_dir),
                str(self.target_dir),
                dry_run=False
            )
        
        test_file = self.create_test_file("test.mp4")
        target_path = self.target_dir / "moved.mp4"
        
        result = organizer.move_file(test_file, target_path)
        
        self.assertTrue(result)
        self.assertFalse(test_file.exists())  # Source should be moved
        self.assertTrue(target_path.exists())  # Target should exist

    def test_move_file_duplicate_handling(self):
        """Test handling of duplicate files."""
        # Create organizer without dry run
        with patch.object(VideoOrganizer, '_check_ffprobe', return_value=True):
            organizer = VideoOrganizer(
                str(self.source_dir),
                str(self.target_dir),
                dry_run=False
            )
        
        # Create target file that already exists
        target_path = self.target_dir / "moved.mp4"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"existing file")
        
        test_file = self.create_test_file("test.mp4")
        
        result = organizer.move_file(test_file, target_path)
        
        self.assertTrue(result)
        self.assertFalse(test_file.exists())  # Source should be moved
        self.assertTrue(target_path.exists())  # Original should still exist
        
        # Check that duplicate was renamed
        expected_duplicate = self.target_dir / "moved_1.mp4"
        self.assertTrue(expected_duplicate.exists())

    @patch('subprocess.run')
    def test_organize_videos_success(self, mock_run):
        """Test successful video organization."""
        # Mock ffprobe output
        mock_metadata = {
            "format": {
                "tags": {
                    "creation_time": "2023-12-25T14:30:22.000000Z"
                }
            }
        }
        mock_run.return_value.stdout = json.dumps(mock_metadata)
        mock_run.return_value.returncode = 0

        # Create test video files
        self.create_test_file("video1.mp4")
        self.create_test_file("video2.mov")
        self.create_test_file("document.txt")  # Should be ignored

        stats = self.organizer.organize_videos()

        self.assertEqual(stats['processed'], 2)
        self.assertEqual(stats['moved'], 2)
        self.assertEqual(stats['skipped'], 0)
        self.assertEqual(stats['errors'], 0)

    @patch('subprocess.run')
    def test_organize_videos_with_errors(self, mock_run):
        """Test video organization with some errors."""
        # Mock ffprobe to fail for some files
        def side_effect(*args, **kwargs):
            if 'video1.mp4' in str(args[0]):
                raise subprocess.CalledProcessError(1, 'ffprobe')
            else:
                result = Mock()
                result.stdout = json.dumps({
                    "format": {
                        "tags": {
                            "creation_time": "2023-12-25T14:30:22.000000Z"
                        }
                    }
                })
                result.returncode = 0
                return result

        mock_run.side_effect = side_effect

        # Create test video files
        self.create_test_file("video1.mp4")  # This will cause error
        self.create_test_file("video2.mov")  # This will succeed

        stats = self.organizer.organize_videos()

        self.assertEqual(stats['processed'], 2)
        self.assertEqual(stats['moved'], 1)
        self.assertEqual(stats['skipped'], 0)
        self.assertEqual(stats['errors'], 1)

    @patch('subprocess.run')
    def test_organize_videos_fallback_to_modification_date(self, mock_run):
        """Test fallback to file modification date when no metadata date found."""
        # Mock ffprobe to return no creation time
        mock_metadata = {
            "format": {
                "tags": {}
            }
        }
        mock_run.return_value.stdout = json.dumps(mock_metadata)
        mock_run.return_value.returncode = 0

        test_file = self.create_test_file("video.mp4")
        
        stats = self.organizer.organize_videos()

        self.assertEqual(stats['processed'], 1)
        self.assertEqual(stats['moved'], 1)
        self.assertEqual(stats['errors'], 0)

    @patch('subprocess.run')
    def test_print_video_metadata(self, mock_run):
        """Test printing video metadata."""
        mock_metadata = {
            "format": {
                "tags": {
                    "creation_time": "2023-12-25T14:30:22.000000Z"
                }
            },
            "streams": []
        }
        mock_run.return_value.stdout = json.dumps(mock_metadata)
        mock_run.return_value.returncode = 0

        test_file = self.create_test_file("test.mp4")
        
        # Capture stdout to verify output
        import io
        from contextlib import redirect_stdout
        
        captured_output = io.StringIO()
        with redirect_stdout(captured_output):
            VideoOrganizer.print_video_metadata(test_file)
        
        output = captured_output.getvalue()
        self.assertIn("Metadata for test.mp4:", output)
        self.assertIn("creation_time", output)

    def test_find_video_files_nested_directories(self):
        """Test finding video files in nested directories."""
        # Create nested directory structure
        nested_dir = self.source_dir / "subdir1" / "subdir2"
        nested_dir.mkdir(parents=True)
        
        # Create video files at different levels
        self.create_test_file("root.mp4")
        self.create_test_file("subdir1/level1.mov")
        self.create_test_file("subdir1/subdir2/level2.avi")
        
        video_files = self.organizer.find_video_files()
        found_names = [f.name for f in video_files]
        
        self.assertEqual(len(video_files), 3)
        self.assertIn("root.mp4", found_names)
        self.assertIn("level1.mov", found_names)
        self.assertIn("level2.avi", found_names)


if __name__ == '__main__':
    unittest.main()
