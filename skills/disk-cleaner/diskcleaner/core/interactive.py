"""
Interactive user interface for cleanup operations.

Provides menu-driven interaction for viewing and selecting files to clean.
"""

import stat
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Tuple

from diskcleaner.core.scanner import FileInfo
from diskcleaner.core.smart_cleanup import CleanupReport, SmartCleanupEngine


class InteractiveCleanupUI:
    """
    Interactive interface for cleanup operations.

    Features:
    - View selection menu (type/risk/age/detailed)
    - Hierarchical display with date ranges and average age
    - File list detail view
    - User selection logic
    """

    def __init__(self, engine: SmartCleanupEngine):
        """
        Initialize interactive UI.

        Args:
            engine: SmartCleanupEngine instance.
        """
        self.engine = engine
        self.selected_files: Set[str] = set()

    def display_report_menu(self, report: CleanupReport) -> Optional[str]:
        """
        Display main menu for report viewing.

        Args:
            report: CleanupReport to display.

        Returns:
            Selected view option, or None if exited.
        """
        while True:
            print("\n" + "=" * 60)
            print("Cleanup report views")
            print("=" * 60)
            print("1. By type")
            print("2. By risk level")
            print("3. By age")
            print("4. Duplicate files")
            print("5. Detailed list")
            print("6. Summary statistics")
            print("0. Back")
            print("=" * 60)

            choice = input("Choose (0-6): ").strip()

            if choice == "0":
                return None
            elif choice in ("1", "2", "3", "4", "5", "6"):
                return choice
            else:
                print("Invalid choice, try again")

    def view_by_type(self, report: CleanupReport) -> List[str]:
        """
        Display files grouped by type and allow selection.

        Args:
            report: CleanupReport to display.

        Returns:
            List of selected file paths.
        """
        selected: Set[str] = set()
        categories = sorted(
            report.by_type.items(),
            key=lambda x: sum(f.size for f in x[1]),
            reverse=True,
        )

        while True:
            print("\n" + "=" * 60)
            print("By type")
            print("=" * 60)

            for idx, (category, files) in enumerate(categories, 1):
                if files:
                    total_size = sum(f.size for f in files)
                    selected_count = sum(1 for f in files if f.path in selected)
                    print(
                        f"{idx}. {category}: {len(files)} files, "
                        f"{self._format_size(total_size)} "
                        f"({selected_count}/{len(files)} selected)"
                    )

            print("\nActions:")
            print("  Enter a number to view the category")
            print("  a. Select all")
            print("  c. Clear selection")
            print("  s. Show selected files")
            print("  0. Back")

            choice = input("\nChoose: ").strip().lower()

            if choice == "0":
                break
            elif choice == "a":
                # Select all
                for _, files in categories:
                    for f in files:
                        selected.add(f.path)
                print(f"\nSelected {len(selected)} files")
            elif choice == "c":
                # Clear selection
                selected.clear()
                print("\nCleared all selections")
            elif choice == "s":
                # Show selected files
                self._display_selected_files(list(selected))
            elif choice.isdigit() and 1 <= int(choice) <= len(categories):
                # Show category details
                idx = int(choice) - 1
                category, files = categories[idx]
                self._display_category_details(category, files, selected)
            else:
                print("Invalid choice")

        return list(selected)

    def view_by_risk(self, report: CleanupReport) -> List[str]:
        """
        Display files grouped by risk level and allow selection.

        Args:
            report: CleanupReport to display.

        Returns:
            List of selected file paths.
        """
        selected: Set[str] = set()

        # Define risk level order and descriptions
        risk_levels = [
            ("safe", "Safe to delete", report.by_risk.get("safe", [])),
            (
                "confirm_needed",
                "Needs confirmation",
                report.by_risk.get("confirm_needed", []),
            ),
            (
                "protected",
                "Protected",
                report.by_risk.get("protected", []),
            ),
        ]

        while True:
            print("\n" + "=" * 60)
            print("By risk level")
            print("=" * 60)

            for idx, (key, label, files) in enumerate(risk_levels, 1):
                if files:
                    total_size = sum(f.size for f in files)
                    selected_count = sum(1 for f in files if f.path in selected)
                    print(
                        f"{idx}. {label}: {len(files)} files, "
                        f"{self._format_size(total_size)} "
                        f"({selected_count}/{len(files)} selected)"
                    )

            print("\nActions:")
            print("  Enter a number to view the category")
            print("  a. Select all safe files")
            print("  c. Clear selection")
            print("  s. Show selected files")
            print("  0. Back")

            choice = input("\nChoose: ").strip().lower()

            if choice == "0":
                break
            elif choice == "a":
                # Select all safe files
                for f in report.by_risk.get("safe", []):
                    selected.add(f.path)
                print(f"\nSelected {len(selected)} files")
            elif choice == "c":
                selected.clear()
                print("\nCleared all selections")
            elif choice == "s":
                self._display_selected_files(list(selected))
            elif choice.isdigit() and 1 <= int(choice) <= len(risk_levels):
                idx = int(choice) - 1
                key, label, files = risk_levels[idx]
                if files:
                    self._display_category_details(label, files, selected)
            else:
                print("Invalid choice")

        return list(selected)

    def view_by_age(self, report: CleanupReport) -> List[str]:
        """
        Display files grouped by age and allow selection.

        Args:
            report: CleanupReport to display.

        Returns:
            List of selected file paths.
        """
        selected: Set[str] = set()
        age_groups = sorted(
            report.by_age.items(),
            key=lambda x: self._get_age_order(x[0]),
        )

        while True:
            print("\n" + "=" * 60)
            print("By age")
            print("=" * 60)

            for idx, (age_group, files) in enumerate(age_groups, 1):
                if files:
                    total_size = sum(f.size for f in files)
                    avg_age = self._calculate_average_age(files)
                    selected_count = sum(1 for f in files if f.path in selected)
                    print(
                        f"{idx}. {age_group}: {len(files)} files, "
                        f"{self._format_size(total_size)}, "
                        f"average age {avg_age:.0f} days "
                        f"({selected_count}/{len(files)} selected)"
                    )

            print("\nActions:")
            print("  Enter a number to view the category")
            print("  a. Select all old files (>30 days)")
            print("  c. Clear selection")
            print("  s. Show selected files")
            print("  0. Back")

            choice = input("\nChoose: ").strip().lower()

            if choice == "0":
                break
            elif choice == "a":
                # Select old files (> 30 days)
                for age_group, files in age_groups:
                    if "over 30 days" in age_group or "90" in age_group:
                        for f in files:
                            selected.add(f.path)
                print(f"\nSelected {len(selected)} files")
            elif choice == "c":
                selected.clear()
                print("\nCleared all selections")
            elif choice == "s":
                self._display_selected_files(list(selected))
            elif choice.isdigit() and 1 <= int(choice) <= len(age_groups):
                idx = int(choice) - 1
                age_group, files = age_groups[idx]
                if files:
                    self._display_category_details(age_group, files, selected)
            else:
                print("Invalid choice")

        return list(selected)

    def view_duplicates(self, report: CleanupReport) -> List[Tuple[str, int]]:
        """
        Display duplicate file groups and allow selection.

        Args:
            report: CleanupReport to display.

        Returns:
            List of (file_path, group_index) tuples for selected duplicates.
        """
        selected: Set[Tuple[str, int]] = set()

        if not report.duplicates:
            print("\nNo duplicate files found")
            return []

        while True:
            print("\n" + "=" * 60)
            print("Duplicate groups")
            print("=" * 60)

            for idx, dup_group in enumerate(report.duplicates[:20], 1):  # Show first 20
                selected_in_group = sum(1 for f in dup_group.files if (f.path, idx) in selected)
                print(
                    f"{idx}. {dup_group.count} duplicate files, "
                    f"{self._format_size(dup_group.size)} each, "
                    f"reclaimable {self._format_size(dup_group.reclaimable_space)} "
                    f"({selected_in_group}/{dup_group.count} selected)"
                )

            if len(report.duplicates) > 20:
                print(f"\n... {len(report.duplicates) - 20} more duplicate groups")

            print("\nActions:")
            print("  Enter a number to view the group")
            print("  a. Select all duplicates (keep 1 per group)")
            print("  c. Clear selection")
            print("  s. Show selected files")
            print("  0. Back")

            choice = input("\nChoose: ").strip().lower()

            if choice == "0":
                break
            elif choice == "a":
                # Select all duplicates (keeping 1 per group)
                for idx, dup_group in enumerate(report.duplicates, 1):
                    # Select all but the first file in each group
                    for file in dup_group.files[1:]:
                        selected.add((file.path, idx))
                print(f"\nSelected {len(selected)} duplicate files")
            elif choice == "c":
                selected.clear()
                print("\nCleared all selections")
            elif choice == "s":
                self._display_selected_duplicates(
                    [(path, idx) for path, idx in selected], report.duplicates
                )
            elif choice.isdigit() and 1 <= int(choice) <= min(len(report.duplicates), 20):
                idx = int(choice)
                dup_group = report.duplicates[idx - 1]
                self._display_duplicate_group_details(idx, dup_group, selected)
            else:
                print("Invalid choice")

        return [(path, idx) for path, idx in selected]

    def view_detailed_list(self, report: CleanupReport) -> List[str]:
        """
        Display detailed list of all files with pagination.

        Args:
            report: CleanupReport to display.

        Returns:
            List of selected file paths.
        """
        selected: Set[str] = set()
        all_files = []
        for files in report.by_type.values():
            all_files.extend(files)

        # Sort by size (descending)
        all_files.sort(key=lambda f: f.size, reverse=True)

        page_size = 20
        current_page = 0
        total_pages = (len(all_files) + page_size - 1) // page_size

        while True:
            print("\n" + "=" * 60)
            print(f"Detailed file list (page {current_page + 1}/{total_pages})")
            print("=" * 60)

            start = current_page * page_size
            end = min(start + page_size, len(all_files))
            page_files = all_files[start:end]

            print(f"{'No.':<6} {'Name':<30} {'Size':>12} {'Modified':<20} {'Sel':<6}")
            print("-" * 80)

            for i, file in enumerate(page_files, start + 1):
                status = "x" if file.path in selected else " "
                mtime_str = datetime.fromtimestamp(file.mtime).strftime("%Y-%m-%d %H:%M")
                print(
                    f"{i:<6} {file.name[:30]:<30} "
                    f"{self._format_size(file.size):>12} "
                    f"{mtime_str:<20} "
                    f"[{status}]"
                )

            print("\nActions:")
            print("  Enter a number to select/deselect a file")
            print("  n. Next page")
            print("  p. Previous page")
            print("  a. Select current page")
            print("  c. Clear all selections")
            print("  s. Show selected files")
            print("  0. Back")

            choice = input(f"\nChoose (page {current_page + 1}): ").strip().lower()

            if choice == "0":
                break
            elif choice == "n" and current_page < total_pages - 1:
                current_page += 1
            elif choice == "p" and current_page > 0:
                current_page -= 1
            elif choice == "a":
                # Select all on current page
                for file in page_files:
                    selected.add(file.path)
                print(f"Selected {len(page_files)} files on this page")
            elif choice == "c":
                selected.clear()
                print("\nCleared all selections")
            elif choice == "s":
                self._display_selected_files(list(selected))
            elif choice.isdigit():
                # Toggle file selection
                idx = int(choice) - 1
                if 0 <= idx < len(all_files):
                    file = all_files[idx]
                    if file.path in selected:
                        selected.remove(file.path)
                    else:
                        selected.add(file.path)
            else:
                print("Invalid choice")

        return list(selected)

    def _display_category_details(
        self, category: str, files: List[FileInfo], selected: Set[str]
    ) -> None:
        """Display details of files in a category."""
        print(f"\n{category} - files")
        print("-" * 80)

        for i, file in enumerate(files[:20], 1):  # Show first 20
            status = "x" if file.path in selected else " "
            mtime_str = datetime.fromtimestamp(file.mtime).strftime("%Y-%m-%d %H:%M")
            print(
                f"{i:3}. [{status}] {file.name:<40} "
                f"{self._format_size(file.size):>12} "
                f"{mtime_str}"
            )

        if len(files) > 20:
            print(f"\n... {len(files) - 20} more files")

        print("\nActions: enter a number to select/deselect, or 0 to go back")
        choice = input("Choose: ").strip()

        if choice.isdigit() and 1 <= int(choice) <= min(len(files), 20):
            idx = int(choice) - 1
            file = files[idx]
            if file.path in selected:
                selected.remove(file.path)
                print(f"\nDeselected: {file.name}")
            else:
                selected.add(file.path)
                print(f"\nSelected: {file.name}")

    def _display_duplicate_group_details(
        self, group_idx: int, dup_group, selected: Set[Tuple[str, int]]
    ) -> None:
        """Display details of duplicate files in a group."""
        print(f"\nDuplicate group #{group_idx}")
        print(f"File size: {self._format_size(dup_group.size)}")
        print(f"Hash: {dup_group.hash_value[:16]}...")
        print("-" * 80)

        for i, file in enumerate(dup_group.files, 1):
            status = "x" if (file.path, group_idx) in selected else " "
            print(f"{i}. [{status}] {file.path}")

        print("\nActions: enter a number to select/deselect a file, or 0 to go back")
        choice = input("Choose: ").strip()

        if choice.isdigit() and 1 <= int(choice) <= len(dup_group.files):
            idx = int(choice) - 1
            file = dup_group.files[idx]
            if (file.path, group_idx) in selected:
                selected.remove((file.path, group_idx))
                print(f"\nDeselected: {file.path}")
            else:
                selected.add((file.path, group_idx))
                print(f"\nSelected: {file.path}")

    def _display_selected_files(self, selected_paths: List[str]) -> None:
        """Display list of selected files."""
        if not selected_paths:
            print("\nNo files selected")
            return

        print(f"\nSelected files ({len(selected_paths)}):")
        print("-" * 80)

        total_size = 0
        for i, path in enumerate(selected_paths[:20], 1):
            file = Path(path)
            print(f"{i:3}. {path}")
            if file.exists():
                total_size += file.stat().st_size

        if len(selected_paths) > 20:
            print(f"\n... {len(selected_paths) - 20} more files")

        print(f"\nTotal: {len(selected_paths)} files, {self._format_size(total_size)}")

    def _display_selected_duplicates(
        self, selected: List[Tuple[str, int]], duplicates: list
    ) -> None:
        """Display list of selected duplicate files."""
        if not selected:
            print("\nNo duplicate files selected")
            return

        print(f"\nSelected duplicate files ({len(selected)}):")
        print("-" * 80)

        for path, group_idx in selected[:20]:
            print(f"Group #{group_idx}: {path}")

        if len(selected) > 20:
            print(f"\n... {len(selected) - 20} more files")

    def _calculate_average_age(self, files: List[FileInfo]) -> float:
        """Calculate average age of files in days."""
        if not files:
            return 0.0

        now = datetime.now()
        total_age = sum((now - datetime.fromtimestamp(f.mtime)).days for f in files)
        return total_age / len(files)

    def _get_age_order(self, age_group: str) -> int:
        """Get sort order for age groups."""
        if "7 days" in age_group:
            return 1
        elif "30 days" in age_group:
            return 2
        elif "90 days" in age_group:
            return 3
        else:
            return 4

    def _format_size(self, size_bytes: int) -> str:
        """Format byte size to human-readable string."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024.0:
                if unit == "B":
                    return f"{size_bytes:,} {unit}"
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    def confirm_and_cleanup(
        self,
        files_to_delete: List[str],
        dry_run: bool = True,
        backup: bool = True,
    ) -> bool:
        """
        Display cleanup summary and request final confirmation.

        Args:
            files_to_delete: List of file paths to delete.
            dry_run: If True, only show what would be deleted.
            backup: If True, create backups before deleting.

        Returns:
            True if cleanup was performed, False if cancelled.
        """
        if not files_to_delete:
            print("\nNo files selected for deletion")
            return False

        # Calculate statistics
        total_size = 0
        valid_files = []

        for file_path in files_to_delete:
            path = Path(file_path)
            if path.exists():
                try:
                    total_size += path.stat().st_size
                    valid_files.append(file_path)
                except OSError:
                    pass

        if not valid_files:
            print("\nThe selected files do not exist or cannot be accessed")
            return False

        # Display cleanup summary
        self._display_cleanup_summary(valid_files, total_size, dry_run)

        # Request final confirmation
        if dry_run:
            print("\n[Preview] No files will be deleted")
            print("To delete, run again without --dry-run")
            return False

        confirmation = input("\nDelete the files above? (type YES to continue): ").strip()

        if confirmation != "YES":
            print("\nCancelled")
            return False

        # Perform cleanup
        print("\nCleaning...")
        success = self._execute_cleanup(valid_files, backup)

        if success:
            print("\n[OK] Cleanup complete")
            print("  Files deleted: {}".format(len(valid_files)))
            print("  Space freed: {}".format(self._format_size(total_size)))
            return True
        else:
            print("\n[X] Errors occurred during cleanup")
            return False

    def _display_cleanup_summary(self, files: List[str], total_size: int, dry_run: bool) -> None:
        """Display cleanup summary before confirmation."""
        print("\n" + "=" * 60)
        print("Cleanup summary")
        print("=" * 60)
        print("{} files will be deleted".format(len(files)))
        print("Space freed: {}".format(self._format_size(total_size)))
        print("Mode: {}".format("Preview (nothing deleted)" if dry_run else "Delete"))
        print("=" * 60)

        # Show first 20 files
        print("\nFiles:")
        for i, file_path in enumerate(files[:20], 1):
            path = Path(file_path)
            size = path.stat().st_size if path.exists() else 0
            print(f"{i:3}. {file_path} ({self._format_size(size)})")

        if len(files) > 20:
            print(f"\n... {len(files) - 20} more files")

        print("\n" + "=" * 60)

    def _execute_cleanup(self, files: List[str], backup: bool) -> bool:
        """
        Execute cleanup operation.

        Args:
            files: List of file paths to delete.
            backup: If True, create backups before deleting.

        Returns:
            True if all files were processed successfully.
        """
        from diskcleaner.core.safety import SafetyChecker, is_protected

        safety_checker = SafetyChecker()
        success_count = 0
        failed_files = []

        for file_path in files:
            try:
                path = Path(file_path)
                # lstat: a link is removed itself, its target is never touched
                metadata = path.lstat()
                is_link = stat.S_ISLNK(metadata.st_mode) or bool(
                    getattr(metadata, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                )

                if not is_link and is_protected(
                    path, safety_checker.protected_paths, safety_checker.protected_extensions
                ):
                    failed_files.append((file_path, "protected path"))
                    continue

                if backup and stat.S_ISREG(metadata.st_mode) and not is_link:
                    if not safety_checker.create_backup(file_path):
                        failed_files.append((file_path, "backup failed, file kept"))
                        continue

                if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
                    path.rmdir()
                else:
                    path.unlink()

                success_count += 1

                # Log deletion
                self._log_deletion(file_path)

            except OSError as e:
                failed_files.append((file_path, str(e)))

        # Report results
        if failed_files:
            print(f"\nWarning: {len(failed_files)} files were not deleted:")
            for file_path, error in failed_files[:10]:
                print(f"  {file_path}: {error}")
            if len(failed_files) > 10:
                print(f"  ... {len(failed_files) - 10} more failures")

        return len(failed_files) == 0

    def _log_deletion(self, file_path: str) -> None:
        """Log file deletion to cleanup log."""
        log_dir = Path.home() / ".disk-cleaner" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / "cleanup.log"

        timestamp = datetime.now().isoformat()
        log_entry = f"{timestamp} | DELETED | {file_path}\n"

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except OSError:
            pass  # Silently fail if can't write log
