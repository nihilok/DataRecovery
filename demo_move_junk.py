#!/usr/bin/env python3
"""
Demo script showing how to use the file extension organizer for PhotoRec recovery.
"""

import tempfile
import shutil
from pathlib import Path
from data_recovery.move_junk import FileExtensionOrganizer

def create_photorec_like_structure():
    """Create a file structure similar to what PhotoRec might generate."""
    temp_dir = Path(tempfile.mkdtemp())
    recovery_dir = temp_dir / "photorec_recovery"
    recovery_dir.mkdir()
    
    # Simulate PhotoRec's scattered file structure
    test_files = [
        # Python files scattered around
        "recup_dir.1/f123456.py",
        "recup_dir.2/f789012.py", 
        "recup_dir.3/f345678.py",
        
        # Java files
        "recup_dir.1/f234567.java",
        "recup_dir.4/f890123.java",
        
        # C/C++ files  
        "recup_dir.2/f456789.c",
        "recup_dir.5/f567890.h",
        "recup_dir.3/f678901.cpp",
        
        # DLL files (from Windows ISO)
        "recup_dir.1/f123890.dll",
        "recup_dir.6/f234901.dll",
        
        # Other files that should be ignored for this demo
        "recup_dir.1/f345012.jpg",
        "recup_dir.2/f456123.txt",
        "recup_dir.7/f567234.mp3",
    ]
    
    print("Creating PhotoRec-like recovery structure...")
    for file_path in test_files:
        full_path = recovery_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add some realistic content based on file type
        if file_path.endswith('.py'):
            full_path.write_text("#!/usr/bin/env python3\nprint('Recovered Python file')\n")
        elif file_path.endswith('.java'):
            full_path.write_text("public class RecoveredClass {\n    // Recovered Java file\n}\n")
        elif file_path.endswith('.c'):
            full_path.write_text("#include <stdio.h>\n// Recovered C file\n")
        elif file_path.endswith('.h'):
            full_path.write_text("#ifndef RECOVERED_H\n#define RECOVERED_H\n// Recovered header\n#endif\n")
        elif file_path.endswith('.cpp'):
            full_path.write_text("#include <iostream>\n// Recovered C++ file\n")
        elif file_path.endswith('.dll'):
            full_path.write_bytes(b"MZ\x90\x00")  # Fake PE header
        else:
            full_path.write_text("Some recovered content")
    
    return temp_dir, recovery_dir

def demo_organization():
    """Demonstrate organizing recovered files."""
    print("File Extension Organizer Demo")
    print("=" * 50)
    print("Simulating PhotoRec data recovery scenario...\n")
    
    # Create the messy structure
    temp_dir, recovery_dir = create_photorec_like_structure()
    
    print(f"Recovery directory: {recovery_dir}")
    print("\nFiles found in recovery (PhotoRec-style structure):")
    
    # Show the messy structure
    for file_path in sorted(recovery_dir.rglob('*')):
        if file_path.is_file():
            relative_path = file_path.relative_to(recovery_dir)
            print(f"  {relative_path}")
    
    print(f"\nTotal files: {len(list(recovery_dir.rglob('*.*')))}")
    
    # Demo 1: Organize Python files only (dry run)
    print("\n" + "="*50)
    print("DEMO 1: Organizing Python files (dry run)")
    print("="*50)
    
    organizer = FileExtensionOrganizer(
        str(recovery_dir),
        str(temp_dir / "organized"),
        ['py'],
        dry_run=True
    )
    
    stats = organizer.organize_files()
    print(f"Would organize {stats['moved']} Python files")
    
    # Demo 2: Organize multiple extensions (dry run)
    print("\n" + "="*50)
    print("DEMO 2: Organizing code files - py, java, c, h, cpp (dry run)")
    print("="*50)
    
    organizer2 = FileExtensionOrganizer(
        str(recovery_dir),
        str(temp_dir / "code_organized"),
        ['py', 'java', 'c', 'h', 'cpp'],
        dry_run=True
    )
    
    stats2 = organizer2.organize_files()
    print(f"Would organize {stats2['moved']} code files total:")
    for ext, count in stats2['by_extension'].items():
        if count > 0:
            print(f"  .{ext}: {count} files")
    
    # Demo 3: Actually organize DLL files to show real output
    print("\n" + "="*50)
    print("DEMO 3: Actually organizing DLL files (real move)")
    print("="*50)
    
    organizer3 = FileExtensionOrganizer(
        str(recovery_dir),
        str(temp_dir / "dll_organized"),
        ['dll'],
        dry_run=False
    )
    
    stats3 = organizer3.organize_files()
    
    # Show the result
    dll_dir = temp_dir / "dll_organized" / "dll_files"
    if dll_dir.exists():
        print(f"\nDLL files moved to: {dll_dir}")
        print("Contents:")
        for file_path in dll_dir.iterdir():
            print(f"  {file_path.name}")
    
    # Clean up
    shutil.rmtree(temp_dir)
    print(f"\nDemo completed. Temporary files cleaned up.")

if __name__ == "__main__":
    demo_organization()
