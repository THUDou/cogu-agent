
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set


def calculate_file_hash(file_path: str, chunk_size: int = 8192) -> Optional[str]:
    try:
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except (IOError, OSError, PermissionError) as e:
        print(f"警告：无法读取文件 {file_path}: {e}", file=sys.stderr)
        return None


def get_file_info(file_path: str) -> Dict:
    try:
        stat = os.stat(file_path)
        modified_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        created_time = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
        return {
            "path": file_path,
            "size": stat.st_size,
            "modified": modified_time,
            "created": created_time,
            "extension": Path(file_path).suffix.lower()
        }
    except (IOError, OSError, PermissionError):
        return {
            "path": file_path,
            "size": 0,
            "modified": "unknown",
            "created": "unknown",
            "extension": "unknown"
        }


def scan_by_content(
    directory: str,
    min_size: int = 1024,
    extensions: Optional[List[str]] = None
) -> Dict[str, List[Dict]]:
    hash_map = {}
    total_files = 0

    if extensions:
        extensions = [ext.lower().lstrip('.') for ext in extensions]

    for root, dirs, files in os.walk(directory):
        for filename in files:
            file_path = os.path.join(root, filename)

            if os.path.islink(file_path):
                continue

            try:
                file_size = os.path.getsize(file_path)
                if file_size < min_size:
                    continue
            except (OSError, PermissionError):
                continue

            if extensions:
                file_ext = Path(filename).suffix.lower().lstrip('.')
                if file_ext not in extensions:
                    continue

            file_hash = calculate_file_hash(file_path)
            if file_hash is None:
                continue

            if file_hash not in hash_map:
                hash_map[file_hash] = []

            hash_map[file_hash].append(get_file_info(file_path))
            total_files += 1

            if total_files % 100 == 0:
                print(f"内容扫描：已处理 {total_files} 个文件...")

    print(f"内容扫描完成！共扫描 {total_files} 个文件")
    return hash_map


def scan_by_metadata(
    directory: str,
    min_size: int = 1024,
    extensions: Optional[List[str]] = None
) -> Dict[str, List[Dict]]:
    metadata_map = {}
    total_files = 0

    if extensions:
        extensions = [ext.lower().lstrip('.') for ext in extensions]

    for root, dirs, files in os.walk(directory):
        for filename in files:
            file_path = os.path.join(root, filename)

            if os.path.islink(file_path):
                continue

            try:
                stat = os.stat(file_path)
                file_size = stat.st_size
                if file_size < min_size:
                    continue
            except (OSError, PermissionError):
                continue

            if extensions:
                file_ext = Path(filename).suffix.lower().lstrip('.')
                if file_ext not in extensions:
                    continue

            file_info = get_file_info(file_path)
            metadata_key = f"{file_info['size']}_{file_info['extension']}_{file_info['modified']}"

            if metadata_key not in metadata_map:
                metadata_map[metadata_key] = []

            metadata_map[metadata_key].append(file_info)
            total_files += 1

            if total_files % 100 == 0:
                print(f"元数据扫描：已处理 {total_files} 个文件...")

    print(f"元数据扫描完成！共扫描 {total_files} 个文件")
    return metadata_map


def merge_scan_results(
    content_map: Dict[str, List[Dict]],
    metadata_map: Dict[str, List[Dict]]
) -> List[Dict]:
    duplicate_groups = []

    for file_hash, files in content_map.items():
        if len(files) > 1:
            sorted_files = sorted(files, key=lambda x: x["modified"])
            duplicate_groups.append({
                "hash": file_hash,
                "match_type": "content",
                "file_size": files[0]["size"],
                "files": sorted_files
            })

    content_hashes = set(content_map.keys())

    for metadata_key, files in metadata_map.items():
        if len(files) > 1:
            already_found = False
            for file in files:
                file_hash = calculate_file_hash(file["path"])
                if file_hash in content_hashes:
                    already_found = True
                    break

            if not already_found:
                sorted_files = sorted(files, key=lambda x: x["modified"])
                duplicate_groups.append({
                    "hash": metadata_key,
                    "match_type": "metadata",
                    "file_size": files[0]["size"],
                    "files": sorted_files
                })

    duplicate_groups.sort(key=lambda x: x["file_size"], reverse=True)

    return duplicate_groups


def generate_report(
    duplicate_groups: List[Dict],
    total_files: int,
    scan_directory: str,
    scan_strategy: str
) -> Dict:
    total_duplicate_files = sum(len(group["files"]) for group in duplicate_groups)
    total_wasted_space = sum(
        (len(group["files"]) - 1) * group["file_size"]
        for group in duplicate_groups
    )

    file_types = {}
    for group in duplicate_groups:
        for file in group["files"]:
            ext = file.get("extension", "unknown")
            file_types[ext] = file_types.get(ext, 0) + 1

    return {
        "openclaw_sdk_version": "2.0.0",
        "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scan_directory": scan_directory,
        "scan_strategy": scan_strategy,
        "status": "success",
        "total_files_scanned": total_files,
        "duplicate_groups_count": len(duplicate_groups),
        "total_duplicate_files": total_duplicate_files,
        "total_wasted_space_bytes": total_wasted_space,
        "total_wasted_space_mb": round(total_wasted_space / (1024 * 1024), 2),
        "file_types": file_types,
        "duplicate_groups": duplicate_groups
    }


def format_size(bytes_size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def print_summary(report: Dict):
    print("\n" + "=" * 60)
    print("扫描摘要")
    print("=" * 60)
    print(f"扫描目录: {report['scan_directory']}")
    print(f"扫描策略: {report['scan_strategy']}")
    print(f"扫描时间: {report['scan_time']}")
    print(f"扫描文件总数: {report['total_files_scanned']}")
    print(f"发现重复组数: {report['duplicate_groups_count']}")
    print(f"重复文件总数: {report['total_duplicate_files']}")
    print(f"可释放空间: {report['total_wasted_space_mb']} MB")

    if report.get('file_types'):
        print("\n文件类型分布:")
        for ext, count in sorted(report['file_types'].items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {ext or '无扩展名'}: {count} 个")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="重复文件扫描器（升级版）- 支持多维度识别",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python duplicate_scanner.py --directory ~/Pictures --output report.json

  python duplicate_scanner.py --directory ~/Documents --strategy content --extensions docx,pdf

  python duplicate_scanner.py --directory ~/Downloads --strategy metadata

  python duplicate_scanner.py --directory ~ --min-size 102400 --output report.json
