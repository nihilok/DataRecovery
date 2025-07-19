# Music File Organizer

A Python script that automatically organizes your music files (MP3 and FLAC) into a logical directory structure based on their ID3 metadata tags. The script reads artist, album, and track information from the files and organizes them into a clean `Artist/Album/Track` hierarchy.

## Features

- **Recursive file discovery**: Finds music files in any nested directory structure
- **Metadata extraction**: Reads ID3 tags from MP3 and FLAC files using the `mutagen` library
- **Smart file naming**: Creates clean, organized filenames with track numbers
- **Duplicate handling**: Automatically renames duplicates by adding numeric suffixes
- **Dry run mode**: Preview what changes will be made without actually moving files
- **Cross-platform**: Works on Windows, macOS, and Linux
- **Logging**: Comprehensive logging of all operations
- **Error handling**: Graceful handling of corrupted files or missing metadata

## Installation

1. Install the required dependency:
```bash
pip install mutagen
```

2. Clone or download this repository to your local machine.

## Usage

### Command Line Interface

The script can be run from the command line with the following syntax:

```bash
python data_recovery/sort_music.py SOURCE_DIR TARGET_DIR [OPTIONS]
```

#### Arguments:
- `SOURCE_DIR`: Directory containing your unsorted music files
- `TARGET_DIR`: Directory where organized music will be placed

#### Options:
- `--dry-run`: Show what would be done without actually moving files
- `--verbose`: Enable detailed logging output

### Examples

1. **Dry run to preview changes**:
```bash
python data_recovery/sort_music.py ./messy_music ./organized_music --dry-run
```

2. **Actually organize the files**:
```bash
python data_recovery/sort_music.py ./messy_music ./organized_music
```

3. **With verbose logging**:
```bash
python data_recovery/sort_music.py ./messy_music ./organized_music --verbose
```

### Programmatic Usage

You can also use the `MusicOrganizer` class directly in your Python code:

```python
from data_recovery.sort_music import MusicOrganizer

# Create organizer instance
organizer = MusicOrganizer(
    source_dir="/path/to/messy/music",
    target_dir="/path/to/organized/music",
    dry_run=True  # Set to False to actually move files
)

# Run the organization
stats = organizer.organize_music()

print(f"Processed: {stats['processed']} files")
print(f"Moved: {stats['moved']} files")
print(f"Errors: {stats['errors']} files")
```

## How It Works

1. **File Discovery**: The script recursively scans the source directory for MP3 and FLAC files
2. **Metadata Extraction**: For each music file, it reads ID3 tags to extract:
   - Artist name
   - Album name
   - Track title
   - Track number
   - Date/Year
   - Genre
3. **Path Generation**: Creates a target path structure: `Artist/Album/TrackNumber - Title.ext`
4. **File Organization**: Moves files to the new location, creating directories as needed
5. **Duplicate Handling**: If a file already exists at the target location, it adds a numeric suffix

## Directory Structure

The script organizes files into this structure:

```
Organized Music/
├── Artist Name/
│   ├── Album Name/
│   │   ├── 01 - Song Title.mp3
│   │   ├── 02 - Another Song.mp3
│   │   └── 03 - Final Track.flac
│   └── Another Album/
│       └── 01 - Solo Track.mp3
└── Different Artist/
    └── Their Album/
        └── 01 - Their Song.flac
```

## Filename Sanitization

The script automatically handles problematic characters in filenames by:
- Replacing invalid characters (`< > : " / \ | ? *`) with underscores
- Removing leading/trailing dots and spaces
- Limiting filename length to 200 characters
- Using "Unknown Artist", "Unknown Album", etc. for missing metadata

## Error Handling

- Files with corrupted or missing metadata are placed in "Unknown Artist/Unknown Album"
- Files that cannot be read are logged as errors but don't stop the process
- Duplicate filenames are handled by adding numeric suffixes (`_1`, `_2`, etc.)

## Supported File Types

Currently supports:
- **MP3** files (with ID3 tags)
- **FLAC** files (with Vorbis comments)

Other file types (JPG, PNG, TXT, etc.) are ignored and left in place.

## Testing

Run the comprehensive test suite:

```bash
python tests/test_sort_music.py
```

The tests cover:
- Filename sanitization
- Metadata extraction from both MP3 and FLAC files
- Target path generation
- File discovery
- Dry run functionality
- Actual file moving
- Duplicate handling
- Integration testing

## Example Run

```bash
$ python data_recovery/sort_music.py ./Downloads/Music ./Music --dry-run

2025-07-19 10:30:15,123 - INFO - Starting music organization...
2025-07-19 10:30:15,124 - INFO - Source: /home/user/Downloads/Music
2025-07-19 10:30:15,124 - INFO - Target: /home/user/Music
2025-07-19 10:30:15,124 - INFO - Dry run: True
2025-07-19 10:30:15,125 - INFO - Found 156 music files
2025-07-19 10:30:15,126 - INFO - DRY RUN: Would move random_song.mp3 -> The Beatles/Abbey Road/01 - Come Together.mp3
2025-07-19 10:30:15,127 - INFO - DRY RUN: Would move track2.flac -> Pink Floyd/Dark Side of the Moon/02 - Breathe.flac
...
2025-07-19 10:30:16,234 - INFO - Organization complete!

==================================================
ORGANIZATION SUMMARY
==================================================
Files processed: 156
Files moved: 156
Files skipped: 0
Errors: 0

This was a dry run - no files were actually moved.
Remove --dry-run to perform the actual organization.
```

## Troubleshooting

### Common Issues:

1. **"mutagen library not found"**: Install with `pip install mutagen`
2. **Permission errors**: Ensure you have read/write access to both source and target directories
3. **Files not found**: Check that the source directory path is correct
4. **Missing metadata**: Files without proper ID3 tags will be placed in "Unknown Artist/Unknown Album"

### Tips:

- Always run with `--dry-run` first to preview changes
- Use `--verbose` for detailed logging when troubleshooting
- The script preserves original ID3 tags - only the file location and name change
- Large collections may take time to process - be patient!

## License

This project is open source. Feel free to modify and distribute as needed.
