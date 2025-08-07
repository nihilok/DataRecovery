# Data Recovery Toolkit

A collection of Python scripts designed to help organize and manage files recovered from data recovery operations. These tools are particularly useful for cleaning up and organizing files recovered by tools like PhotoRec, TestDisk, or similar data recovery software.

## Overview

When data recovery tools extract files from damaged drives, they often dump everything into large directories with cryptic filenames and no organization. This toolkit provides scripts to:

- Analyze file type distributions
- Remove duplicate files
- Organize files by type and metadata
- Split large directories into manageable chunks
- Sort media files by date and metadata

## Scripts

### 1. count_types.py
**File Type Counter**

Recursively scans directories to count and analyze file types by extension.

```bash
python -m data_recovery.count_types /path/to/recovered/files
```

**Features:**
- Counts files by extension
- Provides detailed statistics
- Option to include/exclude hidden files
- Helpful for understanding what was recovered

### 2. deduplicate.py
**Duplicate File Remover**

Finds and removes duplicate files by comparing SHA-256 hashes, keeping only one copy of each unique file.

```bash
python -m data_recovery.deduplicate /path/to/files --dry-run
python -m data_recovery.deduplicate /path/to/files  # Actually remove duplicates
```

**Features:**
- Content-based deduplication using SHA-256 hashes
- Dry-run mode to preview changes
- Preserves the first occurrence of each file
- Essential for cleaning up PhotoRec recoveries

### 3. move_junk.py
**File Extension Organizer**

Moves files with specified extensions into organized directories by file type.

```bash
python -m data_recovery.move_junk /source/dir /target/dir --extensions txt log tmp
```

**Features:**
- Organizes files by extension into separate folders
- Customizable list of extensions to move
- Prevents overwriting with automatic renaming
- Perfect for separating different file types

### 4. sort_music.py
**Music File Organizer**

Organizes MP3 and FLAC files by reading ID3/metadata tags into Artist/Album/Track structure.

```bash
python -m data_recovery.sort_music /path/to/music /organized/music
```

**Features:**
- Reads ID3v2 tags from MP3 files
- Reads metadata from FLAC files
- Creates Artist/Album directory structure
- Handles missing metadata gracefully
- Renames files with track numbers and titles

### 5. sort_photos.py
**Photo File Organizer**

Organizes photos by reading EXIF data and sorting into Year/Month/Date-Time structure.

```bash
python -m data_recovery.sort_photos /path/to/photos /organized/photos --dry-run
```

**Features:**
- Reads EXIF data from images
- Supports multiple image formats (JPEG, PNG, TIFF, etc.)
- Creates Year/Month directory structure
- Falls back to file modification date when EXIF is missing
- Timestamp-based filename prefixes prevent conflicts

### 6. sort_videos.py
**Video File Organizer**

Organizes video files by reading metadata and sorting into Year/Month/Date-Time structure.

```bash
python -m data_recovery.sort_videos /path/to/videos /organized/videos --dry-run
```

**Features:**
- Uses FFmpeg/ffprobe to read video metadata
- Supports many video formats (MP4, MOV, AVI, MKV, etc.)
- Creates Year/Month directory structure
- Falls back to file modification date when metadata is missing
- Requires FFmpeg to be installed

### 7. split_files.py
**Directory Splitter**

Splits large directories into smaller subdirectories with size limits.

```bash
python -m data_recovery.split_files /large/directory --max-size 1GB --dry-run
```

**Features:**
- Splits directories by total file size
- Customizable size limits
- Preserves file organization within splits
- Useful for burning to DVDs or managing large datasets

## Installation

1. Clone or download this repository
2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. For video sorting, install FFmpeg:
   ```bash
   # Ubuntu/Debian
   sudo apt install ffmpeg
   
   # macOS
   brew install ffmpeg
   
   # Windows
   # Download from https://ffmpeg.org/
   ```

## Common Workflow

Here's a typical workflow for organizing recovered files:

1. **Analyze what you have:**
   ```bash
   python -m data_recovery.count_types /recovered/files
   ```

2. **Remove duplicates:**
   ```bash
   python -m data_recovery.deduplicate /recovered/files --dry-run
   python -m data_recovery.deduplicate /recovered/files
   ```

3. **Move unwanted file types:**
   ```bash
   python -m data_recovery.move_junk /recovered/files /junk --extensions tmp log bak
   ```

4. **Organize by media type:**
   ```bash
   python -m data_recovery.sort_photos /recovered/files /organized/photos --dry-run
   python -m data_recovery.sort_videos /recovered/files /organized/videos --dry-run
   python -m data_recovery.sort_music /recovered/files /organized/music --dry-run
   ```

5. **Split if needed:**
   ```bash
   python -m data_recovery.split_files /organized --max-size 4GB
   ```

## Safety Features

- **Dry-run mode**: Most scripts support `--dry-run` to preview changes
- **Automatic backups**: Some scripts can create backups before modifications
- **Duplicate handling**: Automatic renaming prevents file overwrites
- **Comprehensive logging**: Detailed logs of all operations

## Requirements

- Python 3.8+
- PIL/Pillow (for photo EXIF data)
- mutagen (for music metadata)
- FFmpeg (for video metadata)

## Testing

Run the test suite to verify functionality:

```bash
python -m unittest discover tests/
```

## Contributing

Contributions are welcome! Please ensure all new features include tests and follow the existing code style.

## License

This project is open source. See LICENSE file for details.

## Troubleshooting

### Common Issues

**"ffprobe not found" error:**
- Install FFmpeg on your system
- Ensure ffprobe is in your PATH

**Permission errors:**
- Run with appropriate permissions
- Check file/directory ownership

**Out of memory with large files:**
- Use the split_files.py script first
- Process smaller batches

**Metadata not found:**
- Scripts fall back to file modification dates
- Some recovered files may have corrupted metadata
