#!/usr/bin/env python3
"""
Demonstration script for the FileSplitter functionality.
Creates sample files and shows how the splitter works with duplicate handling.
"""

import tempfile
import shutil
from pathlib import Path
from data_recovery.split_files import FileSplitter


def create_demo_files(demo_dir: Path) -> None:
    """Create sample files for demonstration."""
    print("Creating demo files...")

    # Create various file types with different sizes
    files_to_create = [
        ("photo001.jpg", 800),     # 800 MB
        ("photo002.jpg", 600),     # 600 MB
        ("photo003.jpg", 500),     # 500 MB
        ("video001.mp4", 1200),    # 1.2 GB (larger than limit)
        ("document001.pdf", 300),  # 300 MB
        ("document002.pdf", 200),  # 200 MB
        ("backup001.zip", 400),    # 400 MB
        ("backup002.zip", 350),    # 350 MB
        ("music001.mp3", 50),      # 50 MB
        ("music002.mp3", 45),      # 45 MB
        ("music003.mp3", 55),      # 55 MB
    ]

    for filename, size_mb in files_to_create:
        file_path = demo_dir / filename
        # Create file with specified size (using sparse files for efficiency)
        with open(file_path, 'wb') as f:
            f.seek(size_mb * 1024 * 1024 - 1)
            f.write(b'\0')
        print(f"  Created {filename} ({size_mb} MB)")


def demonstrate_duplicate_handling(demo_dir: Path, output_dir: Path) -> None:
    """Demonstrate duplicate filename handling."""
    print("\n=== Demonstrating Duplicate Handling ===")

    # Create some duplicate files in output directory first
    batch_dir = output_dir / "batch_001"
    batch_dir.mkdir(parents=True, exist_ok=True)

    # Create existing files that will conflict
    (batch_dir / "photo001.jpg").write_text("existing photo")
    (batch_dir / "document001.pdf").write_text("existing document")
    print("Created existing files in output directory to test duplicate handling")

    # Create new files with same names in source
    (demo_dir / "photo001.jpg").write_text("new photo content")
    (demo_dir / "document001.pdf").write_text("new document content")
    print("Created new files with duplicate names in source directory")

    # Test duplicate handling
    splitter = FileSplitter(max_size_gb=1.0, dry_run=False)
    files = splitter.scan_directory(demo_dir)
    splits = [files]
    output_dirs = [batch_dir]

    print("Moving files (duplicates will be renamed)...")
    splitter.move_files(splits, output_dirs)

    print("\nResult in output directory:")
    for file_path in sorted(batch_dir.glob("*")):
        print(f"  {file_path.name}")


def main():
    """Run the demonstration."""
    print("=== FileSplitter Demonstration ===\n")

    # Create temporary directories
    demo_base = Path(tempfile.mkdtemp(prefix="file_splitter_demo_"))
    source_dir = demo_base / "source"
    output_dir = demo_base / "output"
    source_dir.mkdir()
    output_dir.mkdir()

    try:
        # Create demo files
        create_demo_files(source_dir)

        print(f"\nCreated demo files in: {source_dir}")

        # Show statistics
        print("\n=== Directory Statistics ===")
        splitter = FileSplitter(max_size_gb=1.0)  # 1GB limit
        stats = splitter.get_statistics(source_dir)

        print(f"Total files: {stats['total_files']}")
        print(f"Total size: {stats['total_size_gb']:.2f} GB")
        print(f"Estimated subdirectories needed: {stats['estimated_subdirs']}")
        print("\nFile types:")
        for ext, count in sorted(stats['file_types'].items()):
            print(f"  {ext}: {count} files")

        # Demonstrate dry run
        print("\n=== Dry Run (Preview) ===")
        dry_splitter = FileSplitter(max_size_gb=1.0, dry_run=True)
        dry_splitter.split_directory(source_dir, output_dir)

        print(f"\nFiles still in source after dry run: {len(list(source_dir.glob('*')))}")
        print(f"Directories created in output: {len(list(output_dir.glob('batch_*')))}")

        # Clean up for actual run
        shutil.rmtree(output_dir)
        output_dir.mkdir()

        # Demonstrate actual splitting
        print("\n=== Actual File Splitting ===")
        actual_splitter = FileSplitter(max_size_gb=1.0, dry_run=False)
        actual_splitter.split_directory(source_dir, output_dir)

        # Show results
        print("\n=== Results ===")
        batch_dirs = sorted(output_dir.glob("batch_*"))
        print(f"Created {len(batch_dirs)} subdirectories:")

        for batch_dir in batch_dirs:
            files_in_batch = list(batch_dir.glob("*"))
            total_size = sum(f.stat().st_size for f in files_in_batch) / (1024**3)
            print(f"\n{batch_dir.name}: {len(files_in_batch)} files, {total_size:.2f} GB")
            for file_path in sorted(files_in_batch):
                file_size = file_path.stat().st_size / (1024**2)
                print(f"  {file_path.name} ({file_size:.0f} MB)")

        # Reset for duplicate demo
        shutil.rmtree(source_dir)
        shutil.rmtree(output_dir)
        source_dir.mkdir()
        output_dir.mkdir()

        # Demonstrate duplicate handling
        demonstrate_duplicate_handling(source_dir, output_dir)

        print(f"\n=== Cleanup ===")
        print(f"Demo files created in: {demo_base}")
        print("You can examine the results or run:")
        print(f"rm -rf {demo_base}")
        print("to clean up when finished.")

    except Exception as e:
        print(f"Error during demonstration: {e}")
        print(f"Cleaning up: {demo_base}")
        shutil.rmtree(demo_base)


if __name__ == "__main__":
    main()
