#!/usr/bin/env python3
"""
重复文件扫描器（升级版）
扫描指定目录，支持多维度重复文件识别
- 内容识别：基于文件哈希值
- 元数据识别：基于文件名、大小、修改时间
- 智能合并：综合多种识别结果
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set


def calculate_file_hash(file_path: str, chunk_size: int = 8192) -> Optional[str]:
    """
    计算文件的MD5哈希值

    Args:
        file_path: 文件路径
        chunk_size: 每次读取的块大小

    Returns:
        文件的MD5哈希值，如果出错返回None
    """
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
    """
    获取文件信息

    Args:
        file_path: 文件路径

    Returns:
        包含文件信息的字典
    """
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
    """
    基于文件内容（哈希值）扫描重复文件

    Args:
        directory: 要扫描的目录
        min_size: 最小文件大小（字节）
        extensions: 文件扩展名过滤列表

    Returns:
        字典，键为哈希值，值为文件信息列表
    """
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
    """
    基于元数据（文件名、大小、修改时间）扫描重复文件

    Args:
        directory: 要扫描的目录
        min_size: 最小文件大小（字节）
        extensions: 文件扩展名过滤列表

    Returns:
        字典，键为元数据签名，值为文件信息列表
    """
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

            # 创建元数据签名（文件名+大小+修改时间）
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
    """
    合并多种扫描结果

    Args:
        content_map: 内容扫描结果
        metadata_map: 元数据扫描结果

    Returns:
        合并后的重复文件组列表
    """
    # 使用内容识别的结果作为基础
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

    # 补充仅在元数据中发现的重复文件（内容不同但元数据相同）
    content_hashes = set(content_map.keys())

    for metadata_key, files in metadata_map.items():
        if len(files) > 1:
            # 检查这些文件是否已经在内容识别中被发现
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

    # 按文件大小降序排序
    duplicate_groups.sort(key=lambda x: x["file_size"], reverse=True)

    return duplicate_groups


def generate_report(
    duplicate_groups: List[Dict],
    total_files: int,
    scan_directory: str,
    scan_strategy: str
) -> Dict:
    """
    生成扫描报告（OpenClaw SDK兼容格式）

    Args:
        duplicate_groups: 重复文件组列表
        total_files: 扫描的文件总数
        scan_directory: 扫描的目录
        scan_strategy: 扫描策略

    Returns:
        包含扫描结果的字典
    """
    total_duplicate_files = sum(len(group["files"]) for group in duplicate_groups)
    total_wasted_space = sum(
        (len(group["files"]) - 1) * group["file_size"]
        for group in duplicate_groups
    )

    # 统计文件类型
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
    """
    格式化文件大小

    Args:
        bytes_size: 字节大小

    Returns:
        格式化后的字符串（如 "1.23 MB"）
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def print_summary(report: Dict):
    """
    打印扫描摘要

    Args:
        report: 扫描报告
    """
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
  # 使用综合识别策略（默认）
  python duplicate_scanner.py --directory ~/Pictures --output report.json

  # 仅使用内容识别
  python duplicate_scanner.py --directory ~/Documents --strategy content --extensions docx,pdf

  # 使用元数据识别（更快）
  python duplicate_scanner.py --directory ~/Downloads --strategy metadata

  # 扫描大于100KB的文件
  python duplicate_scanner.py --directory ~ --min-size 102400 --output report.json
        """
    )

    parser.add_argument(
        "--directory",
        required=True,
        help="要扫描的目录路径"
    )

    parser.add_argument(
        "--output",
        help="输出报告文件路径（JSON格式）"
    )

    parser.add_argument(
        "--strategy",
        choices=["comprehensive", "content", "metadata"],
        default="comprehensive",
        help="识别策略：comprehensive(综合), content(内容), metadata(元数据)"
    )

    parser.add_argument(
        "--min-size",
        type=int,
        default=1024,
        help="最小文件大小（字节），默认1024（1KB）"
    )

    parser.add_argument(
        "--extensions",
        help="文件扩展名过滤，逗号分隔（如 jpg,png,gif）"
    )

    args = parser.parse_args()

    # 验证目录
    if not os.path.isdir(args.directory):
        print(f"错误：目录不存在或无法访问: {args.directory}", file=sys.stderr)
        sys.exit(1)

    # 解析扩展名列表
    extensions = None
    if args.extensions:
        extensions = [ext.strip() for ext in args.extensions.split(',')]

    print(f"开始扫描目录: {args.directory}")
    print(f"识别策略: {args.strategy}")
    print(f"最小文件大小: {args.min_size} 字节")
    if extensions:
        print(f"文件类型过滤: {', '.join(extensions)}")
    print("-" * 60)

    # 执行扫描
    content_map = {}
    metadata_map = {}
    total_files = 0

    if args.strategy in ["content", "comprehensive"]:
        content_map = scan_by_content(args.directory, args.min_size, extensions)

    if args.strategy in ["metadata", "comprehensive"]:
        metadata_map = scan_by_metadata(args.directory, args.min_size, extensions)

    # 合并结果
    if args.strategy == "comprehensive":
        duplicate_groups = merge_scan_results(content_map, metadata_map)
    elif args.strategy == "content":
        duplicate_groups = [
            {
                "hash": h,
                "match_type": "content",
                "file_size": files[0]["size"],
                "files": sorted(files, key=lambda x: x["modified"])
            }
            for h, files in content_map.items()
            if len(files) > 1
        ]
    else:  # metadata
        duplicate_groups = [
            {
                "hash": k,
                "match_type": "metadata",
                "file_size": files[0]["size"],
                "files": sorted(files, key=lambda x: x["modified"])
            }
            for k, files in metadata_map.items()
            if len(files) > 1
        ]

    # 按文件大小排序
    duplicate_groups.sort(key=lambda x: x["file_size"], reverse=True)

    # 计算总文件数
    total_files = 0
    if args.strategy in ["content", "comprehensive"]:
        total_files += sum(len(files) for files in content_map.values())
    if args.strategy == "metadata" or (args.strategy == "comprehensive" and not content_map):
        total_files = sum(len(files) for files in metadata_map.values())

    # 生成报告
    report = generate_report(
        duplicate_groups,
        total_files,
        args.directory,
        args.strategy
    )

    # 打印摘要
    print_summary(report)

    # 输出结果
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\n详细报告已保存到: {args.output}")
        except IOError as e:
            print(f"错误：无法写入输出文件: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("\n详细报告:")
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
