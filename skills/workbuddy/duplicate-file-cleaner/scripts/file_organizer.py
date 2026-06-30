
import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class SmartFileOrganizer:

    def __init__(self):
        self.stats = {
            "total_files": 0,
            "organized_files": 0,
            "skipped_files": 0,
            "error_files": 0
        }

    def organize_by_type(self, directory: str, output_dir: str) -> Dict:
        file_categories = {
            "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".svg"],
            "Documents": [".doc", ".docx", ".pdf", ".txt", ".rtf", ".odt", ".pages"],
            "Spreadsheets": [".xls", ".xlsx", ".csv", ".ods"],
            "Presentations": [".ppt", ".pptx", ".odp", ".key"],
            "Audio": [".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg"],
            "Video": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"],
            "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
            "Code": [".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".php", ".rb", ".go"],
            "Executables": [".exe", ".msi", ".app", ".dmg", ".deb", ".rpm"],
            "Fonts": [".ttf", ".otf", ".woff", ".woff2", ".eot"],
            "E-books": [".epub", ".mobi", ".azw3", ".lit"]
        }

        return self._organize(directory, output_dir, file_categories, "type")

    def organize_by_date(self, directory: str, output_dir: str, date_type: str = "modified") -> Dict:
        categories = {}

        for root, dirs, files in os.walk(directory):
            for filename in files:
                file_path = os.path.join(root, filename)

                if os.path.islink(file_path):
                    continue

                try:
                    if date_type == "modified":
                        timestamp = os.path.getmtime(file_path)
                    else:
                        timestamp = os.path.getctime(file_path)

                    date_obj = datetime.fromtimestamp(timestamp)
                    category = date_obj.strftime("%Y-%m")

                    if category not in categories:
                        categories[category] = []

                    categories[category].append(file_path)
                except (OSError, IOError):
                    continue

        return self._organize_by_categories(directory, output_dir, categories, "date")

    def organize_by_size(self, directory: str, output_dir: str) -> Dict:
        file_categories = {
            "Small (< 1MB)": [],
            "Medium (1MB - 100MB)": [],
            "Large (100MB - 1GB)": [],
            "Very Large (> 1GB)": []
        }

        for root, dirs, files in os.walk(directory):
            for filename in files:
                file_path = os.path.join(root, filename)

                if os.path.islink(file_path):
                    continue

                try:
                    file_size = os.path.getsize(file_path)
                    size_mb = file_size / (1024 * 1024)

                    if size_mb < 1:
                        file_categories["Small (< 1MB)"].append(file_path)
                    elif size_mb < 100:
                        file_categories["Medium (1MB - 100MB)"].append(file_path)
                    elif size_mb < 1024:
                        file_categories["Large (100MB - 1GB)"].append(file_path)
                    else:
                        file_categories["Very Large (> 1GB)"].append(file_path)
                except (OSError, IOError):
                    continue

        return self._organize_by_categories(directory, output_dir, file_categories, "size")

    def _organize(self, directory: str, output_dir: str,
                  categories: Dict[str, List[str]], strategy: str) -> Dict:
        file_map = {category: [] for category in categories}

        for root, dirs, files in os.walk(directory):
            for filename in files:
                file_path = os.path.join(root, filename)

                if os.path.islink(file_path):
                    continue

                ext = Path(filename).suffix.lower()

                for category, extensions in categories.items():
                    if ext in extensions:
                        file_map[category].append(file_path)
                        break

        return self._organize_by_categories(directory, output_dir, file_map, strategy)

    def _organize_by_categories(self, directory: str, output_dir: str,
                                file_map: Dict[str, List[str]], strategy: str) -> Dict:
        result = {
            "strategy": strategy,
            "source_directory": directory,
            "output_directory": output_dir,
            "categories": {},
            "stats": self.stats.copy(),
            "organize_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        for category, files in file_map.items():
            if not files:
                continue

            category_dir = os.path.join(output_dir, category)
            os.makedirs(category_dir, exist_ok=True)

            category_result = {
                "category_name": category,
                "file_count": len(files),
                "files": []
            }

            for file_path in files:
                self.stats["total_files"] += 1

                try:
                    filename = os.path.basename(file_path)
                    dest_path = os.path.join(category_dir, filename)

                    if os.path.exists(dest_path):
                        base, ext = os.path.splitext(filename)
                        counter = 1
                        while os.path.exists(os.path.join(category_dir, f"{base}_{counter}{ext}")):
                            counter += 1
                        dest_path = os.path.join(category_dir, f"{base}_{counter}{ext}")

                    if not self._dry_run:
                        shutil.move(file_path, dest_path)

                    self.stats["organized_files"] += 1
                    category_result["files"].append({
                        "source": file_path,
                        "destination": dest_path,
                        "status": "moved"
                    })
                except Exception as e:
                    self.stats["error_files"] += 1
                    category_result["files"].append({
                        "source": file_path,
                        "status": "error",
                        "error": str(e)
                    })

            result["categories"][category] = category_result

        result["stats"] = self.stats.copy()
        return result

    def __init__(self):
        self._dry_run = True
        self.stats = {
            "total_files": 0,
            "organized_files": 0,
            "skipped_files": 0,
            "error_files": 0
        }


def load_scan_result(input_file: str) -> Optional[Dict]:
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"错误：无法读取扫描结果文件: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(
        description="智能文件整理器 - 按不同策略整理文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python file_organizer.py --directory ~/Downloads --output ~/Organized --strategy type

  python file_organizer.py --directory ~/Pictures --output ~/Organized --strategy date

  python file_organizer.py --directory ~/Documents --output ~/Organized --strategy size --dry-run

  python file_organizer.py --directory ~/Downloads --output ~/Organized --strategy type --execute
