#!/usr/bin/env python3
"""
Tests for the music organizer script.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import os
import sys

# Add the parent directory to the Python path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_recovery.sort_music import MusicOrganizer


class TestMusicOrganizer(unittest.TestCase):
    """Test cases for MusicOrganizer class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.source_dir = self.temp_dir / "source"
        self.target_dir = self.temp_dir / "target"
        self.source_dir.mkdir()
        self.target_dir.mkdir()

        self.organizer = MusicOrganizer(
            str(self.source_dir),
            str(self.target_dir),
            dry_run=True
        )

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        test_cases = [
            ("Normal File.mp3", "Normal File.mp3"),
            ("File<with>bad:chars", "File_with_bad_chars"),
            ('File"with|more?bad*chars', "File_with_more_bad_chars"),
            ("   .Leading dots and spaces   ", "Leading dots and spaces"),
            ("", "Unknown"),
            ("A" * 250, "A" * 200),  # Length limit
        ]

        for input_name, expected in test_cases:
            with self.subTest(input_name=input_name):
                result = self.organizer.sanitize_filename(input_name)
                self.assertEqual(result, expected)

    def test_extract_metadata_mp3(self):
        """Test metadata extraction from MP3 files."""
        # Create a mock MP3 file with metadata
        mock_metadata = {
            'TPE1': ['Test Artist'],
            'TALB': ['Test Album'],
            'TIT2': ['Test Title'],
            'TRCK': ['1/10'],
            'TDRC': ['2023']
        }

        with patch('data_recovery.sort_music.MutagenFile') as mock_mutagen:
            mock_file = Mock()
            mock_file.__contains__ = lambda self, key: key in mock_metadata
            mock_file.__getitem__ = lambda self, key: mock_metadata[key]
            mock_mutagen.return_value = mock_file

            test_file = self.source_dir / "test.mp3"
            test_file.touch()

            metadata = self.organizer.extract_metadata(test_file)

            expected = {
                'artist': 'Test Artist',
                'album': 'Test Album',
                'title': 'Test Title',
                'track': '1/10',
                'date': '2023'
            }

            self.assertEqual(metadata, expected)

    def test_extract_metadata_flac(self):
        """Test metadata extraction from FLAC files."""
        mock_metadata = {
            'ARTIST': ['FLAC Artist'],
            'ALBUM': ['FLAC Album'],
            'TITLE': ['FLAC Title'],
            'TRACKNUMBER': ['2'],
        }

        with patch('data_recovery.sort_music.MutagenFile') as mock_mutagen:
            mock_file = Mock()
            mock_file.__contains__ = lambda self, key: key in mock_metadata
            mock_file.__getitem__ = lambda self, key: mock_metadata[key]
            mock_mutagen.return_value = mock_file

            test_file = self.source_dir / "test.flac"
            test_file.touch()

            metadata = self.organizer.extract_metadata(test_file)

            expected = {
                'artist': 'FLAC Artist',
                'album': 'FLAC Album',
                'title': 'FLAC Title',
                'track': '2'
            }

            self.assertEqual(metadata, expected)

    def test_extract_metadata_no_file(self):
        """Test metadata extraction when file cannot be read."""
        with patch('data_recovery.sort_music.MutagenFile') as mock_mutagen:
            mock_mutagen.return_value = None

            test_file = self.source_dir / "invalid.mp3"
            test_file.touch()

            metadata = self.organizer.extract_metadata(test_file)
            self.assertEqual(metadata, {})

    def test_generate_target_path(self):
        """Test target path generation."""
        test_file = Path("test.mp3")

        # Test with complete metadata
        metadata = {
            'artist': 'The Beatles',
            'album': 'Abbey Road',
            'title': 'Come Together',
            'track': '1'
        }

        target_path = self.organizer.generate_target_path(test_file, metadata)
        expected = self.target_dir / "The Beatles" / "Abbey Road" / "01 - Come Together.mp3"
        self.assertEqual(target_path, expected)

        # Test with track number containing total tracks
        metadata['track'] = '1/10'
        target_path = self.organizer.generate_target_path(test_file, metadata)
        expected = self.target_dir / "The Beatles" / "Abbey Road" / "01 - Come Together.mp3"
        self.assertEqual(target_path, expected)

        # Test with missing metadata
        metadata = {}
        target_path = self.organizer.generate_target_path(test_file, metadata)
        expected = self.target_dir / "Unknown Artist" / "Unknown Album" / "test.mp3"
        self.assertEqual(target_path, expected)

        # Test with problematic characters
        metadata = {
            'artist': 'AC/DC',
            'album': 'Back in Black: Remastered',
            'title': 'Highway to Hell?',
            'track': '5'
        }
        target_path = self.organizer.generate_target_path(test_file, metadata)
        expected = self.target_dir / "AC_DC" / "Back in Black_ Remastered" / "05 - Highway to Hell_.mp3"
        self.assertEqual(target_path, expected)

    def test_find_music_files(self):
        """Test finding music files recursively."""
        # Create test file structure
        music_files = [
            "song1.mp3",
            "song2.flac",
            "subdir/song3.mp3",
            "deep/nested/song4.flac"
        ]

        other_files = [
            "image.jpg",
            "readme.txt",
            "cover.png"
        ]

        # Create music files
        for file_path in music_files:
            full_path = self.source_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.touch()

        # Create non-music files
        for file_path in other_files:
            full_path = self.source_dir / file_path
            full_path.touch()

        found_files = self.organizer.find_music_files()
        found_names = [f.name for f in found_files]

        # Should find only music files
        expected_names = ["song1.mp3", "song2.flac", "song3.mp3", "song4.flac"]
        self.assertEqual(sorted(found_names), sorted(expected_names))
        self.assertEqual(len(found_files), 4)

    def test_move_file_dry_run(self):
        """Test file moving in dry run mode."""
        source_file = self.source_dir / "test.mp3"
        source_file.touch()

        target_file = self.target_dir / "Artist" / "Album" / "01 - Song.mp3"

        # Should return True for dry run
        result = self.organizer.move_file(source_file, target_file)
        self.assertTrue(result)

        # File should still exist in source
        self.assertTrue(source_file.exists())

        # Target directory should not be created in dry run
        self.assertFalse(target_file.parent.exists())

    def test_move_file_actual(self):
        """Test actual file moving."""
        # Create organizer without dry run
        organizer = MusicOrganizer(
            str(self.source_dir),
            str(self.target_dir),
            dry_run=False
        )

        source_file = self.source_dir / "test.mp3"
        source_file.write_text("test content")

        target_file = self.target_dir / "Artist" / "Album" / "01 - Song.mp3"

        result = organizer.move_file(source_file, target_file)

        self.assertTrue(result)
        self.assertFalse(source_file.exists())
        self.assertTrue(target_file.exists())
        self.assertEqual(target_file.read_text(), "test content")

    def test_move_file_duplicate_handling(self):
        """Test handling of duplicate files."""
        organizer = MusicOrganizer(
            str(self.source_dir),
            str(self.target_dir),
            dry_run=False
        )

        # Create existing target file
        target_file = self.target_dir / "Artist" / "Album" / "01 - Song.mp3"
        target_file.parent.mkdir(parents=True)
        target_file.write_text("existing content")

        # Create source file
        source_file = self.source_dir / "test.mp3"
        source_file.write_text("new content")

        result = organizer.move_file(source_file, target_file)

        self.assertTrue(result)
        self.assertFalse(source_file.exists())

        # Original file should be unchanged
        self.assertEqual(target_file.read_text(), "existing content")

        # New file should be renamed
        renamed_file = self.target_dir / "Artist" / "Album" / "01 - Song_1.mp3"
        self.assertTrue(renamed_file.exists())
        self.assertEqual(renamed_file.read_text(), "new content")

    @patch('data_recovery.sort_music.MutagenFile')
    def test_organize_music_integration(self, mock_mutagen):
        """Test the complete organization process."""
        # Set up mock metadata
        mock_metadata = {
            'TPE1': ['Test Artist'],
            'TALB': ['Test Album'],
            'TIT2': ['Test Song'],
            'TRCK': ['1']
        }

        mock_file = Mock()
        mock_file.__contains__ = lambda self, key: key in mock_metadata
        mock_file.__getitem__ = lambda self, key: mock_metadata[key]
        mock_mutagen.return_value = mock_file

        # Create test files
        test_files = [
            "song1.mp3",
            "subdir/song2.flac",
            "image.jpg"  # Should be ignored
        ]

        for file_path in test_files:
            full_path = self.source_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.touch()

        # Run organization
        stats = self.organizer.organize_music()

        # Check statistics
        self.assertEqual(stats['processed'], 2)  # Only music files
        self.assertEqual(stats['moved'], 2)
        self.assertEqual(stats['errors'], 0)


class TestCommandLineInterface(unittest.TestCase):
    """Test the command line interface."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.source_dir = self.temp_dir / "source"
        self.target_dir = self.temp_dir / "target"
        self.source_dir.mkdir()

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    @patch('data_recovery.sort_music.MusicOrganizer')
    @patch('sys.argv', ['sort_music.py', 'source', 'target', '--dry-run'])
    def test_main_dry_run(self, mock_organizer_class):
        """Test main function with dry run."""
        from data_recovery.sort_music import main

        # Mock the organizer
        mock_organizer = Mock()
        mock_organizer.organize_music.return_value = {
            'processed': 5,
            'moved': 5,
            'skipped': 0,
            'errors': 0
        }
        mock_organizer_class.return_value = mock_organizer

        with patch('data_recovery.sort_music.Path') as mock_path:
            mock_path.return_value.exists.return_value = True

            result = main()

            self.assertEqual(result, 0)
            mock_organizer_class.assert_called_once_with('source', 'target', True)
            mock_organizer.organize_music.assert_called_once()


if __name__ == '__main__':
    # Create a test suite
    test_suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))

    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # Exit with appropriate code
    exit(0 if result.wasSuccessful() else 1)
