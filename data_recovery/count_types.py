#!/usr/bin/env python3
"""
Count different file types in a nested directory structure recursively.
"""

import os
import argparse
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List


def get_file_extension(filepath: Path) -> str:
    """
    Get the file extension from a filepath.
    Returns lowercase extension without the dot, or 'no_extension' if none.
    """
    if filepath.suffix:
        return filepath.suffix.lower().lstrip('.')
    return 'no_extension'


def count_file_types(directory: str, include_hidden: bool = False) -> Dict[str, int]:
    """
    Count file types recursively in a directory.

    Args:
        directory: Path to the directory to scan
        include_hidden: Whether to include hidden files (starting with .)

    Returns:
        Dictionary mapping file extensions to their counts
    """
    file_counts = Counter()
    directory_path = Path(directory)

    if not directory_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not directory_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {directory}")

    # Walk through directory recursively
    for root, dirs, files in os.walk(directory_path):
        # Filter out hidden directories if not including hidden files
        if not include_hidden:
            dirs[:] = [d for d in dirs if not d.startswith('.')]

        for file in files:
            # Skip hidden files if not including them
            if not include_hidden and file.startswith('.'):
                continue

            filepath = Path(root) / file
            extension = get_file_extension(filepath)
            file_counts[extension] += 1

    return dict(file_counts)


def get_file_details(directory: str, include_hidden: bool = False) -> Dict[str, List[str]]:
    """
    Get detailed information about files grouped by extension.

    Args:
        directory: Path to the directory to scan
        include_hidden: Whether to include hidden files

    Returns:
        Dictionary mapping extensions to lists of file paths
    """
    file_details = defaultdict(list)
    directory_path = Path(directory)

    for root, dirs, files in os.walk(directory_path):
        if not include_hidden:
            dirs[:] = [d for d in dirs if not d.startswith('.')]

        for file in files:
            if not include_hidden and file.startswith('.'):
                continue

            filepath = Path(root) / file
            extension = get_file_extension(filepath)
            relative_path = filepath.relative_to(directory_path)
            file_details[extension].append(str(relative_path))

    return dict(file_details)


def format_results(file_counts: Dict[str, int], show_details: bool = False,
                  file_details: Dict[str, List[str]] = None) -> str:
    """
    Format the results for display.

    Args:
        file_counts: Dictionary of extension -> count
        show_details: Whether to show individual file paths
        file_details: Dictionary of extension -> file paths (required if show_details=True)

    Returns:
        Formatted string representation of results
    """
    if not file_counts:
        return "No files found in the directory."

    # Sort by count (descending) then by extension name
    sorted_items = sorted(file_counts.items(), key=lambda x: (-x[1], x[0]))

    total_files = sum(file_counts.values())

    result = [f"File Type Count Summary (Total: {total_files} files)", "=" * 50]

    for extension, count in sorted_items:
        percentage = (count / total_files) * 100
        ext_display = extension if extension != 'no_extension' else '(no extension)'
        result.append(f"{ext_display:15} : {count:6} files ({percentage:5.1f}%)")

        if show_details and file_details and extension in file_details:
            for filepath in sorted(file_details[extension])[:10]:  # Show max 10 examples
                result.append(f"    └── {filepath}")
            if len(file_details[extension]) > 10:
                result.append(f"    └── ... and {len(file_details[extension]) - 10} more")
            result.append("")

    return "\n".join(result)


def main():
    """Main function to handle command line arguments and execute the counting."""
    parser = argparse.ArgumentParser(
        description="Count file types recursively in a directory structure"
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to scan (default: current directory)"
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include hidden files and directories (starting with .)"
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Show example file paths for each extension"
    )
    parser.add_argument(
        "--output",
        help="Output file to save results (optional)"
    )

    args = parser.parse_args()

    try:
        # Count file types
        file_counts = count_file_types(args.directory, args.include_hidden)

        # Get file details if requested
        file_details = None
        if args.details:
            file_details = get_file_details(args.directory, args.include_hidden)

        # Format and display results
        results = format_results(file_counts, args.details, file_details)

        print(results)

        # Save to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                f.write(results)
            print(f"\nResults saved to: {args.output}")

    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
