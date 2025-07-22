#!/usr/bin/env python3
"""
Example usage of the music organizer script.
This demonstrates how to use the MusicOrganizer class programmatically.
"""

import tempfile
from pathlib import Path
from data_recovery.sort_music import MusicOrganizer

def create_sample_music_files():
    """Create some sample music files for demonstration."""
    temp_dir = Path(tempfile.mkdtemp())
    source_dir = temp_dir / "messy_music"
    source_dir.mkdir()

    # Create some sample files (empty files for demo)
    sample_files = [
        "random_song.mp3",
        "another_track.flac",
        "music/some_album_track.mp3",
        "downloads/best_song_ever.flac",
        "old_files/nested/deep/classic.mp3",
        "cover.jpg",  # This will be ignored
        "readme.txt"  # This will be ignored
    ]

    for file_path in sample_files:
        full_path = source_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.touch()

    return temp_dir, source_dir

def main():
    """Demonstrate the music organizer."""
    print("Music Organizer Example")
    print("=" * 50)

    # Create sample files
    temp_dir, source_dir = create_sample_music_files()
    target_dir = temp_dir / "organized_music"

    print(f"Source directory: {source_dir}")
    print(f"Target directory: {target_dir}")
    print()

    # Show what files we have
    print("Files in source directory:")
    for file_path in source_dir.rglob('*'):
        if file_path.is_file():
            relative_path = file_path.relative_to(source_dir)
            print(f"  {relative_path}")
    print()

    # Run in dry-run mode first
    print("Running in DRY-RUN mode...")
    organizer = MusicOrganizer(str(source_dir), str(target_dir), dry_run=True)
    stats = organizer.organize_music()

    print(f"\nDry run results:")
    print(f"  Files processed: {stats['processed']}")
    print(f"  Files that would be moved: {stats['moved']}")
    print(f"  Errors: {stats['errors']}")

    # Clean up
    import shutil
    shutil.rmtree(temp_dir)
    print(f"\nDemo completed. Temporary files cleaned up.")

if __name__ == "__main__":
    main()
