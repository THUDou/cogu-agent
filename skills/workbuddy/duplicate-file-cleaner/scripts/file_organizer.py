#!/usr/bin/env python3
"""
智能文件整理器
根据不同策略整理文件到指定目录
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class SmartFileOrganizer:
    """智能文件整理器"""

    def __init__(self):
        self.stats = {
            "total_files": 0,
            "organized_files": 0,
            "skipped_files": 0,
            "error_files": 0
        }

    def organize_by_type(self, directory: str, output_dir: str) -> Dict:
        """
        按文件类型整理

        Args:
            directory: 源目录
            output_dir: 输出目录

        Returns:
            整理结果
        """
        file_categories = {
            # 图片
            "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".svg"],
            # 文档
            "Documents": [".doc", ".docx", ".pdf", ".txt", ".rtf", ".odt", ".pages"],
            # 表格
            "Spreadsheets": [".xls", ".xlsx", ".csv", ".ods"],
            # 演示文稿
            "Presentations": [".ppt", ".pptx", ".odp", ".key"],
            # 音频
            "Audio": [".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg"],
            # 视频
            "Video": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"],
            # 压缩包
            "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
            # 代码
            "Code": [".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".php", ".rb", ".go"],
            # 可执行文件
            "Executables": [".exe", ".msi", ".app", ".dmg", ".deb", ".rpm"],
            # 字体
            "Fonts": [".ttf", ".otf", ".woff", ".woff2", ".eot"],
            # 电子书
            "E-books": [".epub", ".mobi", ".azw3", ".lit"]
        }

        return self._organize(directory, output_dir, file_categories, "type")

    def organize_by_date(self, directory: str, output_dir: str, date_type: str = "modified") -> Dict:
        """
        按日期整理

        Args:
            directory: 源目录
            output_dir: 输出目录
            date_type: 日期类型（modified/created）

        Returns:
            整理结果
        """
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
        """
        按文件大小整理

        Args:
            directory: 源目录
            output_dir: 输出目录

        Returns:
            整理结果
        """
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
        """
        按分类规则整理文件

        Args:
            directory: 源目录
            output_dir: 输出目录
            categories: 分类规则（扩展名映射）
            strategy: 整理策略

        Returns:
            整理结果
        """
        # 收集文件
        file_map = {category: [] for category in categories}

        for root, dirs, files in os.walk(directory):
            for filename in files:
                file_path = os.path.join(root, filename)

                if os.path.islink(file_path):
                    continue

                ext = Path(filename).suffix.lower()

                # 查找文件所属分类
                for category, extensions in categories.items():
                    if ext in extensions:
                        file_map[category].append(file_path)
                        break

        return self._organize_by_categories(directory, output_dir, file_map, strategy)

    def _organize_by_categories(self, directory: str, output_dir: str,
                                file_map: Dict[str, List[str]], strategy: str) -> Dict:
        """
        按分类整理文件

        Args:
            directory: 源目录
            output_dir: 输出目录
            file_map: 文件分类映射
            strategy: 整理策略

        Returns:
            整理结果
        """
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

            # 创建分类目录
            category_dir = os.path.join(output_dir, category)
            os.makedirs(category_dir, exist_ok=True)

            category_result = {
                "category_name": category,
                "file_count": len(files),
                "files": []
            }

            # 移动文件
            for file_path in files:
                self.stats["total_files"] += 1

                try:
                    filename = os.path.basename(file_path)
                    dest_path = os.path.join(category_dir, filename)

                    # 处理文件名冲突
                    if os.path.exists(dest_path):
                        base, ext = os.path.splitext(filename)
                        counter = 1
                        while os.path.exists(os.path.join(category_dir, f"{base}_{counter}{ext}")):
                            counter += 1
                        dest_path = os.path.join(category_dir, f"{base}_{counter}{ext}")

                    # 移动文件（模拟模式）
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
    """加载扫描结果"""
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
  # 按文件类型整理
  python file_organizer.py --directory ~/Downloads --output ~/Organized --strategy type

  # 按修改日期整理
  python file_organizer.py --directory ~/Pictures --output ~/Organized --strategy date

  # 按文件大小整理（预览模式）
  python file_organizer.py --directory ~/Documents --output ~/Organized --strategy size --dry-run

  # 真正执行整理
  python file_organizer.py --directory ~/Downloads --output ~/Organized --strategy type --execute
        """
    )

    parser.add_argument(
        "--directory",
        required=True,
        help="要整理的源目录"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="输出目录"
    )

    parser.add_argument(
        "--strategy",
        choices=["type", "date", "size"],
        default="type",
        help="整理策略：type(按类型), date(按日期), size(按大小)"
    )

    parser.add_argument(
        "--date-type",
        choices=["modified", "created"],
        default="modified",
        help="日期类型（仅当strategy=date时有效）"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式（不实际移动文件）"
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行模式（实际移动文件，默认为预览模式）"
    )

    parser.add_argument(
        "--output-file",
        help="输出整理报告文件路径（JSON格式）"
    )

    args = parser.parse_args()

    # 验证目录
    if not os.path.isdir(args.directory):
        print(f"错误：源目录不存在或无法访问: {args.directory}", file=sys.stderr)
        sys.exit(1)

    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)

    # 创建整理器
    organizer = SmartFileOrganizer()

    # 设置执行模式
    if args.execute:
        organizer._dry_run = False
        mode = "执行模式"
    else:
        mode = "预览模式"

    print(f"开始整理（{mode}）...")
    print(f"源目录: {args.directory}")
    print(f"输出目录: {args.output}")
    print(f"整理策略: {args.strategy}")
    print("-" * 60)

    # 执行整理
    if args.strategy == "type":
        result = organizer.organize_by_type(args.directory, args.output)
    elif args.strategy == "date":
        result = organizer.organize_by_date(args.directory, args.output, args.date_type)
    elif args.strategy == "size":
        result = organizer.organize_by_size(args.directory, args.output)
    else:
        print(f"错误：不支持的整理策略: {args.strategy}", file=sys.stderr)
        sys.exit(1)

    # 输出结果
    print(f"整理完成！")
    print(f"总文件数: {result['stats']['total_files']}")
    print(f"已整理: {result['stats']['organized_files']}")
    print(f"错误: {result['stats']['error_files']}")
    print("-" * 60)

    for category, data in result["categories"].items():
        print(f"{category}: {data['file_count']} 个文件")

    # 保存报告
    if args.output_file:
        try:
            with open(args.output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n详细报告已保存到: {args.output_file}")
        except IOError as e:
            print(f"错误：无法写入输出文件: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("\n详细报告:")
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
