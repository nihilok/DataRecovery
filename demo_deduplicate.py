#!/usr/bin/env python3
"""
Demonstration script for the deduplication functionality.
Shows how to find and remove duplicate photos across batch directories.
"""

import tempfile
import shutil
from pathlib import Path
from data_recovery.deduplicate import FileDuplicateRemover
import hashlib


def create_demo_photos(demo_dir: Path) -> None:
    """Create sample photo files with some duplicates."""
    print("Creating demo photo files...")
    
    # Create batch directories (simulating split_files output)
    batch1_dir = demo_dir / "batch_001"
    batch2_dir = demo_dir / "batch_002" 
    batch3_dir = demo_dir / "batch_003"
    
    for batch_dir in [batch1_dir, batch2_dir, batch3_dir]:
        batch_dir.mkdir(parents=True, exist_ok=True)
    
    # Create unique photo content
    photo_contents = {
        "sunset.jpg": b"beautiful sunset photo content",
        "mountain.jpg": b"majestic mountain landscape content", 
        "beach.jpg": b"tropical beach vacation content",
        "family.jpg": b"family portrait photo content",
        "pet.jpg": b"cute pet photo content"
    }
    
    # Batch 1: Original photos
    for filename, content in photo_contents.items():
        (batch1_dir / filename).write_bytes(content)
        print(f"  Created batch_001/{filename}")
    
    # Batch 2: Some duplicates + new photos
    # Duplicate sunset and mountain from batch 1
    (batch2_dir / "sunset_copy.jpg").write_bytes(photo_contents["sunset.jpg"])
    (batch2_dir / "mountain_duplicate.jpg").write_bytes(photo_contents["mountain.jpg"])
    # New unique photos
    (batch2_dir / "concert.jpg").write_bytes(b"live concert photo content")
    (batch2_dir / "garden.jpg").write_bytes(b"beautiful garden photo content")
    print(f"  Created batch_002/ with 2 duplicates + 2 new photos")
    
    # Batch 3: More duplicates
    # Duplicate beach from batch 1
    (batch3_dir / "vacation_beach.jpg").write_bytes(photo_contents["beach.jpg"])
    # Duplicate family from batch 1 
    (batch3_dir / "family_portrait.jpg").write_bytes(photo_contents["family.jpg"])
    # Duplicate concert from batch 2
    (batch3_dir / "music_event.jpg").write_bytes(b"live concert photo content")
    # New unique photo
    (batch3_dir / "cityscape.jpg").write_bytes(b"urban cityscape photo content")
    print(f"  Created batch_003/ with 3 duplicates + 1 new photo")
    
    print(f"\nTotal files created: {sum(len(list(d.glob('*'))) for d in [batch1_dir, batch2_dir, batch3_dir])}")


def demonstrate_basic_deduplication(demo_dir: Path) -> None:
    """Demonstrate basic duplicate detection and removal."""
    print("\n=== Basic Duplicate Detection ===")
    
    # First, show what's in each directory
    for batch_dir in sorted(demo_dir.glob("batch_*")):
        files = list(batch_dir.glob("*.jpg"))
        print(f"{batch_dir.name}: {len(files)} files")
        for file_path in files:
            size_kb = file_path.stat().st_size / 1024
            print(f"  - {file_path.name} ({size_kb:.1f} KB)")
    
    # Scan for duplicates
    print("\nScanning for duplicates...")
    deduplicator = FileDuplicateRemover(dry_run=True)  # Dry run first
    deduplicator.scan_directory(demo_dir, include_patterns=["*.jpg", "*.jpeg", "*.png"])
    
    duplicates = deduplicator.find_duplicates()
    
    if duplicates:
        print(f"\nFound {len(duplicates)} sets of duplicate photos:")
        for i, (file_hash, duplicate_files) in enumerate(duplicates.items(), 1):
            print(f"\nDuplicate Set #{i} (hash: {file_hash[:16]}...):")
            for file_path in duplicate_files:
                print(f"  - {file_path}")
    else:
        print("\nNo duplicates found!")


def demonstrate_removal_strategies(demo_dir: Path) -> None:
    """Demonstrate different strategies for choosing which duplicate to keep."""
    print("\n=== Duplicate Removal Strategies ===")
    
    strategies = ["shortest_path", "oldest", "newest", "first_alphabetical"]
    
    for strategy in strategies:
        print(f"\n--- Strategy: {strategy} ---")
        
        # Create a fresh copy for each strategy test
        strategy_dir = demo_dir / f"test_{strategy}"
        if strategy_dir.exists():
            shutil.rmtree(strategy_dir)
        shutil.copytree(demo_dir, strategy_dir, ignore=shutil.ignore_patterns("test_*"))
        
        # Run deduplication with this strategy
        deduplicator = FileDuplicateRemover(dry_run=True)
        deduplicator.scan_directory(strategy_dir, include_patterns=["*.jpg"])
        duplicates = deduplicator.find_duplicates()
        
        if duplicates:
            print("Files that would be kept:")
            for file_hash, duplicate_files in duplicates.items():
                keeper = deduplicator.choose_file_to_keep(duplicate_files, strategy)
                print(f"  KEEP: {keeper}")
                for dup in duplicate_files:
                    if dup != keeper:
                        print(f"  remove: {dup}")


def demonstrate_report_generation(demo_dir: Path) -> None:
    """Demonstrate generating a detailed duplicate report."""
    print("\n=== Report Generation ===")
    
    deduplicator = FileDuplicateRemover(dry_run=True)
    deduplicator.scan_directory(demo_dir, include_patterns=["*.jpg"])
    duplicates = deduplicator.find_duplicates()
    
    # Generate report
    report_file = demo_dir / "duplicate_report.txt"
    report = deduplicator.generate_report(duplicates, report_file)
    
    print(f"Generated detailed report: {report_file}")
    print("\nReport preview:")
    print("-" * 40)
    # Show first few lines of the report
    lines = report.split('\n')
    for line in lines[:15]:  # Show first 15 lines
        print(line)
    if len(lines) > 15:
        print("... (truncated)")


def demonstrate_actual_removal(demo_dir: Path) -> None:
    """Demonstrate actually removing duplicates."""
    print("\n=== Actual Duplicate Removal ===")
    
    # Create a copy for actual removal
    removal_dir = demo_dir / "removal_test"
    if removal_dir.exists():
        shutil.rmtree(removal_dir)
    shutil.copytree(demo_dir, removal_dir, ignore=shutil.ignore_patterns("test_*", "duplicate_report.txt"))
    
    print("Before removal:")
    total_before = sum(len(list(d.glob("*.jpg"))) for d in removal_dir.glob("batch_*"))
    print(f"Total photos: {total_before}")
    
    # Actually remove duplicates
    deduplicator = FileDuplicateRemover(dry_run=False)  # Real removal
    deduplicator.scan_directory(removal_dir, include_patterns=["*.jpg"])
    duplicates = deduplicator.find_duplicates()
    deduplicator.remove_duplicates(duplicates, keep_strategy="shortest_path")
    
    print("\nAfter removal:")
    total_after = sum(len(list(d.glob("*.jpg"))) for d in removal_dir.glob("batch_*"))
    print(f"Total photos: {total_after}")
    print(f"Duplicates removed: {total_before - total_after}")
    
    print("\nRemaining files:")
    for batch_dir in sorted(removal_dir.glob("batch_*")):
        files = list(batch_dir.glob("*.jpg"))
        if files:
            print(f"{batch_dir.name}: {len(files)} files")
            for file_path in files:
                print(f"  - {file_path.name}")


def demonstrate_hash_database(demo_dir: Path) -> None:
    """Demonstrate saving and loading hash database for large collections."""
    print("\n=== Hash Database Feature ===")
    
    # Scan and save hash database
    deduplicator = FileDuplicateRemover()
    deduplicator.scan_directory(demo_dir, include_patterns=["*.jpg"])
    
    # Save hash database
    hash_db_file = demo_dir / "photo_hashes.json"
    deduplicator.save_hash_database(hash_db_file)
    print(f"Saved hash database: {hash_db_file}")
    
    # Load hash database in new instance
    new_deduplicator = FileDuplicateRemover(dry_run=True)
    new_deduplicator.load_hash_database(hash_db_file)
    
    duplicates = new_deduplicator.find_duplicates()
    print(f"Loaded database: {new_deduplicator.processed_files} files, {len(duplicates)} duplicate sets")
    
    print("\nThis feature is useful for:")
    print("- Large photo collections (avoid re-scanning)")
    print("- Comparing new photos against existing collection")
    print("- Backup verification")


def main():
    """Run the demonstration."""
    print("=== Photo Deduplication Demonstration ===\n")
    
    # Create temporary directory for demo
    demo_base = Path(tempfile.mkdtemp(prefix="photo_dedup_demo_"))
    
    try:
        # Create demo files
        create_demo_photos(demo_base)
        
        # Run demonstrations
        demonstrate_basic_deduplication(demo_base)
        demonstrate_removal_strategies(demo_base) 
        demonstrate_report_generation(demo_base)
        demonstrate_actual_removal(demo_base)
        demonstrate_hash_database(demo_base)
        
        print(f"\n=== Usage Examples ===")
        print("To use the deduplication script on your actual batch directories:")
        print()
        print("# Preview what would be removed (dry run)")
        print("python -m data_recovery.deduplicate /path/to/batch_dirs --dry-run --include '*.jpg' '*.png'")
        print()
        print("# Generate a detailed report")
        print("python -m data_recovery.deduplicate /path/to/batch_dirs --report duplicates.txt --dry-run")
        print()
        print("# Actually remove duplicates (keep files with shortest paths)")
        print("python -m data_recovery.deduplicate /path/to/batch_dirs --include '*.jpg' '*.png'")
        print()
        print("# Remove duplicates keeping newest files")
        print("python -m data_recovery.deduplicate /path/to/batch_dirs --keep-strategy newest")
        print()
        print("# Save hash database for future use")
        print("python -m data_recovery.deduplicate /path/to/photos --save-hashes photo_hashes.json --dry-run")
        
        print(f"\n=== Demo Files Location ===")
        print(f"Demo created in: {demo_base}")
        print("You can examine the results or clean up with:")
        print(f"rm -rf {demo_base}")
        
    except Exception as e:
        print(f"Error during demonstration: {e}")
        shutil.rmtree(demo_base)


if __name__ == "__main__":
    main()
