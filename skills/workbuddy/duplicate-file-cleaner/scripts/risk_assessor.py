
import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional


class RiskAssessmentEngine:

    HIGH_RISK_DIRECTORIES = [
        "/System", "/usr/bin", "/etc", "/var",
        "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)"
    ]

    SENSITIVE_EXTENSIONS = [
        ".docx", ".xlsx", ".pptx", ".pdf", ".exe", ".dll", ".so", ".dylib"
    ]

    def __init__(self):
        self.risk_factors = []

    def assess_risk(self, scan_result: Dict) -> Dict:
        risk_score = 0
        self.risk_factors = []

        risk_score += self._assess_file_count(scan_result)

        risk_score += self._assess_file_types(scan_result)

        risk_score += self._assess_directory_location(scan_result)

        risk_score += self._assess_duplicate_groups(scan_result)

        risk_score += self._assess_file_sizes(scan_result)

        risk_level = self._determine_risk_level(risk_score)
        recommendation = self._generate_recommendation(risk_level, scan_result)

        return {
            "risk_level": risk_level,
            "risk_score": min(risk_score, 100),
            "risk_factors": self.risk_factors,
            "recommendation": recommendation,
            "assessment_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def _assess_file_count(self, scan_result: Dict) -> int:
        total_files = scan_result.get("total_files_scanned", 0)
        duplicate_count = scan_result.get("total_duplicate_files", 0)

        if duplicate_count > 1000:
            self.risk_factors.append(f"重复文件数量过多: {duplicate_count} 个")
            return 30
        elif duplicate_count > 100:
            self.risk_factors.append(f"重复文件数量较多: {duplicate_count} 个")
            return 15
        elif duplicate_count > 10:
            return 5
        else:
            return 0

    def _assess_file_types(self, scan_result: Dict) -> int:
        risk_score = 0
        sensitive_count = 0

        for group in scan_result.get("duplicate_groups", []):
            for file_info in group["files"]:
                ext = os.path.splitext(file_info["path"])[1].lower()
                if ext in self.SENSITIVE_EXTENSIONS:
                    sensitive_count += 1

        if sensitive_count > 50:
            self.risk_factors.append(f"包含大量敏感文件: {sensitive_count} 个")
            risk_score = 25
        elif sensitive_count > 10:
            self.risk_factors.append(f"包含敏感文件: {sensitive_count} 个")
            risk_score = 10
        elif sensitive_count > 0:
            risk_score = 5

        return risk_score

    def _assess_directory_location(self, scan_result: Dict) -> int:
        directory = scan_result.get("scan_directory", "")
        risk_score = 0

        for risky_dir in self.HIGH_RISK_DIRECTORIES:
            if directory.startswith(risky_dir):
                self.risk_factors.append(f"扫描高风险目录: {directory}")
                return 30

        if any(keyword in directory for keyword in ["/Documents", "/Desktop", "Documents", "Desktop"]):
            self.risk_factors.append(f"扫描重要用户目录: {directory}")
            risk_score = 15
        elif any(keyword in directory for keyword in ["/Downloads", "Downloads"]):
            risk_score = 5  # Downloads目录风险较低

        return risk_score

    def _assess_duplicate_groups(self, scan_result: Dict) -> int:
        group_count = scan_result.get("duplicate_groups_count", 0)

        if group_count > 100:
            self.risk_factors.append(f"重复文件组过多: {group_count} 组")
            return 15
        elif group_count > 20:
            return 5
        else:
            return 0

    def _assess_file_sizes(self, scan_result: Dict) -> int:
        wasted_space = scan_result.get("total_wasted_space_bytes", 0)
        wasted_mb = wasted_space / (1024 * 1024)

        if wasted_mb > 10000:  # 超过10GB
            self.risk_factors.append(f"可释放空间过大: {wasted_mb:.2f} MB")
            return 10
        elif wasted_mb > 1000:  # 超过1GB
            return 5
        else:
            return 0

    def _determine_risk_level(self, risk_score: int) -> str:
        if risk_score >= 70:
            return "high"
        elif risk_score >= 40:
            return "medium"
        else:
            return "low"

    def _generate_recommendation(self, risk_level: str, scan_result: Dict) -> str:
        duplicate_count = scan_result.get("total_duplicate_files", 0)
        wasted_mb = scan_result.get("total_wasted_space_mb", 0)

        if risk_level == "high":
            return (f"⚠️ 高风险操作！发现 {duplicate_count} 个重复文件，"
                    f"可释放 {wasted_mb:.2f} MB 空间。\n"
                    f"建议：手动选择需要删除的文件，并确保已创建备份。")
        elif risk_level == "medium":
            return (f"⚡ 中等风险。发现 {duplicate_count} 个重复文件，"
                    f"可释放 {wasted_mb:.2f} MB 空间。\n"
                    f"建议：谨慎清理，建议创建备份后再进行操作。")
        else:
            return (f"✅ 低风险操作。发现 {duplicate_count} 个重复文件，"
                    f"可释放 {wasted_mb:.2f} MB 空间。\n"
                    f"建议：可以安全清理，但仍建议先查看确认。")


def load_scan_result(input_file: str) -> Optional[Dict]:
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"错误：无法读取扫描结果文件: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(
        description="风险评估引擎 - 评估文件清理操作的风险",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python risk_assessor.py --input scan_report.json

  python risk_assessor.py --input scan_report.json --output risk_report.json

  cat scan_report.json | python risk_assessor.py
