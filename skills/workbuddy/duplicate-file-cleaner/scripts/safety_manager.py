
import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class SafetyManager:

    def __init__(self, backup_dir: Optional[str] = None):
        self.backup_dir = backup_dir or os.path.expanduser("~/.file_cleaner_backup")
        self.log_dir = os.path.join(self.backup_dir, "logs")
        self.history_file = os.path.join(self.backup_dir, "history.json")
        self._ensure_directories()

    def _ensure_directories(self):
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

    def backup_files(self, file_list: List[str], operation_id: Optional[str] = None) -> Dict:
        if not operation_id:
            operation_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        backup_path = os.path.join(self.backup_dir, f"backup_{operation_id}")
        os.makedirs(backup_path, exist_ok=True)

        result = {
            "operation_id": operation_id,
            "backup_path": backup_path,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_files": len(file_list),
            "backup_success": 0,
            "backup_failed": 0,
            "files": []
        }

        for file_path in file_list:
            if not os.path.exists(file_path):
                result["backup_failed"] += 1
                result["files"].append({
                    "original_path": file_path,
                    "status": "skipped",
                    "reason": "file_not_exists"
                })
                continue

            try:
                filename = os.path.basename(file_path)
                dest_path = os.path.join(backup_path, filename)

                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(os.path.join(backup_path, f"{base}_{counter}{ext}")):
                        counter += 1
                    dest_path = os.path.join(backup_path, f"{base}_{counter}{ext}")

                shutil.copy2(file_path, dest_path)

                result["backup_success"] += 1
                result["files"].append({
                    "original_path": file_path,
                    "backup_path": dest_path,
                    "status": "success"
                })
            except Exception as e:
                result["backup_failed"] += 1
                result["files"].append({
                    "original_path": file_path,
                    "status": "failed",
                    "error": str(e)
                })

        self._record_history("backup", operation_id, result)

        return result

    def restore_files(self, operation_id: str, restore_to_original: bool = True) -> Dict:
        backup_info_file = os.path.join(
            self.backup_dir, f"backup_{operation_id}", "backup_info.json"
        )

        if not os.path.exists(backup_info_file):
            return {
                "status": "error",
                "message": f"找不到备份信息: {operation_id}"
            }

        try:
            with open(backup_info_file, 'r', encoding='utf-8') as f:
                backup_info = json.load(f)
        except Exception as e:
            return {
                "status": "error",
                "message": f"无法读取备份信息: {e}"
            }

        result = {
            "operation_id": operation_id,
            "restore_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_files": 0,
            "restore_success": 0,
            "restore_failed": 0,
            "files": []
        }

        for file_info in backup_info["files"]:
            if file_info["status"] != "success":
                continue

            result["total_files"] += 1

            try:
                backup_path = file_info["backup_path"]

                if restore_to_original:
                    original_path = file_info["original_path"]
                    os.makedirs(os.path.dirname(original_path), exist_ok=True)
                else:
                    restore_dir = os.path.join(self.backup_dir, "restored", operation_id)
                    os.makedirs(restore_dir, exist_ok=True)
                    original_path = os.path.join(restore_dir, os.path.basename(backup_path))

                shutil.copy2(backup_path, original_path)

                result["restore_success"] += 1
                result["files"].append({
                    "backup_path": backup_path,
                    "restore_path": original_path,
                    "status": "success"
                })
            except Exception as e:
                result["restore_failed"] += 1
                result["files"].append({
                    "backup_path": backup_path,
                    "status": "failed",
                    "error": str(e)
                })

        self._record_history("restore", operation_id, result)

        return result

    def list_backups(self) -> Dict:
        backups = []

        if not os.path.exists(self.backup_dir):
            return {"backups": []}

        for item in os.listdir(self.backup_dir):
            if item.startswith("backup_") and os.path.isdir(os.path.join(self.backup_dir, item)):
                backup_path = os.path.join(self.backup_dir, item)
                operation_id = item.replace("backup_", "")

                try:
                    backup_info_file = os.path.join(backup_path, "backup_info.json")
                    if os.path.exists(backup_info_file):
                        with open(backup_info_file, 'r', encoding='utf-8') as f:
                            info = json.load(f)
                            backups.append({
                                "operation_id": operation_id,
                                "timestamp": info.get("timestamp"),
                                "total_files": info.get("total_files"),
                                "backup_path": backup_path
                            })
                except Exception:
                    continue

        backups.sort(key=lambda x: x["timestamp"], reverse=True)

        return {"backups": backups}

    def delete_files_safely(self, file_list: List[str], backup_first: bool = True,
                           operation_id: Optional[str] = None) -> Dict:
        if not operation_id:
            operation_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        result = {
            "operation_id": operation_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_files": len(file_list),
            "delete_success": 0,
            "delete_failed": 0,
            "backup": None,
            "files": []
        }

        if backup_first:
            backup_result = self.backup_files(file_list, operation_id)
            result["backup"] = backup_result

            if backup_result["backup_success"] < len(file_list):
                print("警告：部分文件备份失败，删除操作已取消", file=sys.stderr)
                return result

        for file_path in file_list:
            try:
                os.remove(file_path)
                result["delete_success"] += 1
                result["files"].append({
                    "file_path": file_path,
                    "status": "deleted"
                })
            except Exception as e:
                result["delete_failed"] += 1
                result["files"].append({
                    "file_path": file_path,
                    "status": "failed",
                    "error": str(e)
                })

        self._record_history("delete", operation_id, result)

        return result

    def _record_history(self, operation_type: str, operation_id: str, result: Dict):
        history = []

        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except Exception:
                pass

        history.append({
            "operation_type": operation_type,
            "operation_id": operation_id,
            "timestamp": result.get("timestamp"),
            "status": "success"
        })

        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"警告：无法记录操作历史: {e}", file=sys.stderr)

    def cleanup_old_backups(self, days: int = 30) -> Dict:
        result = {
            "cleanup_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "days_to_keep": days,
            "deleted_backups": 0,
            "failed_deletions": 0,
            "details": []
        }

        if not os.path.exists(self.backup_dir):
            return result

        cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)

        for item in os.listdir(self.backup_dir):
            if item.startswith("backup_") and os.path.isdir(os.path.join(self.backup_dir, item)):
                backup_path = os.path.join(self.backup_dir, item)

                try:
                    backup_time = os.path.getmtime(backup_path)

                    if backup_time < cutoff_time:
                        shutil.rmtree(backup_path)
                        result["deleted_backups"] += 1
                        result["details"].append({
                            "backup": item,
                            "status": "deleted"
                        })
                except Exception as e:
                    result["failed_deletions"] += 1
                    result["details"].append({
                        "backup": item,
                        "status": "failed",
                        "error": str(e)
                    })

        return result


def main():
    parser = argparse.ArgumentParser(
        description="安全管理器 - 提供文件操作的安全保障",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python safety_manager.py --list-backups

  python safety_manager.py --backup --files file1.txt,file2.jpg

  python safety_manager.py --restore --operation-id 20240101_120000

  python safety_manager.py --delete --files file1.txt,file2.jpg --backup-first

  python safety_manager.py --cleanup --days 30
