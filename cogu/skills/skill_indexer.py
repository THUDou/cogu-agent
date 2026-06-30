"""Skill渐进式披露索引器 — 参考万悟openapi2skill/mcp2skill

核心能力:
  - 扫描所有SKILL.md，生成摘要索引
  - 按级别返回内容（summary/detail/full）
  - FTS5全文搜索
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cogu.skills.skill_schema import SkillManifest, DisclosureLevel


@dataclass
class SkillIndexEntry:
    """索引条目 — 每个skill的摘要"""
    name: str = ""
    version: str = ""
    description: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    risk_level: str = "low"
    source: str = ""
    indexed_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "risk_level": self.risk_level,
            "source": self.source,
            "indexed_at": self.indexed_at,
        }


class SkillIndexer:
    """Skill渐进式披露索引器

    参考万悟openapi2skill/mcp2skill的渐进式披露设计:
      - summary: 仅name+description+tags（用于快速浏览）
      - detail: +persona+recipes+steps（用于决策）
      - full: 完整SKILL.md内容（用于执行）
    """

    def __init__(self, db_path: str = ""):
        if db_path:
            self._db_path = db_path
        else:
            self._db_path = str(Path.home() / ".cogu" / "skill_index.db")
        self._manifests: dict[str, SkillManifest] = {}
        self._entries: dict[str, SkillIndexEntry] = {}
        self._init_db()

    def _init_db(self):
        """初始化FTS5搜索数据库"""
        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS skill_fts (
                name TEXT PRIMARY KEY,
                description TEXT,
                category TEXT,
                tags TEXT,
                persona_role TEXT,
                recipe_names TEXT,
                risk_level TEXT,
                full_content TEXT
            )
        """)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS skill_search USING fts5(
                name,
                description,
                category,
                tags,
                persona_role,
                recipe_names,
                content=skill_fts,
                content_rowid=rowid
            )
        """)
        conn.commit()
        conn.close()

    def build_index(self, skills_dir: str) -> dict:
        """扫描所有SKILL.md，生成摘要索引

        Args:
            skills_dir: skill根目录，递归扫描所有SKILL.md

        Returns:
            索引统计 {"total": N, "new": N, "updated": N, "errors": N}
        """
        stats = {"total": 0, "new": 0, "updated": 0, "errors": 0}
        base = Path(skills_dir)
        if not base.is_dir():
            return stats

        for skill_md in base.rglob("SKILL.md"):
            stats["total"] += 1
            try:
                manifest = SkillManifest.from_markdown(str(skill_md))
                if not manifest or not manifest.name:
                    stats["errors"] += 1
                    continue

                is_new = manifest.name not in self._manifests
                if is_new:
                    stats["new"] += 1
                else:
                    stats["updated"] += 1

                self._manifests[manifest.name] = manifest
                self._entries[manifest.name] = SkillIndexEntry(
                    name=manifest.name,
                    version=manifest.version,
                    description=manifest.description,
                    category=manifest.category.value,
                    tags=manifest.tags,
                    risk_level=manifest.risk_level.value,
                    source=manifest.source,
                    indexed_at=time.time(),
                )
                self._update_fts(manifest)
            except Exception:
                stats["errors"] += 1

        return stats

    def _update_fts(self, manifest: SkillManifest):
        """更新FTS5索引"""
        conn = sqlite3.connect(self._db_path)
        try:
            persona_role = manifest.persona.role.value if manifest.persona else ""
            recipe_names = ",".join(r.name for r in manifest.recipes)
            tags_str = ",".join(manifest.tags)
            full_content = manifest.to_skill_md()

            conn.execute("DELETE FROM skill_fts WHERE name = ?", (manifest.name,))
            conn.execute(
                """INSERT INTO skill_fts (name, description, category, tags,
                   persona_role, recipe_names, risk_level, full_content)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (manifest.name, manifest.description, manifest.category.value,
                 tags_str, persona_role, recipe_names, manifest.risk_level.value, full_content),
            )
            conn.execute("DELETE FROM skill_search WHERE name = ?", (manifest.name,))
            conn.execute(
                """INSERT INTO skill_search (name, description, category, tags,
                   persona_role, recipe_names)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (manifest.name, manifest.description, manifest.category.value,
                 tags_str, persona_role, recipe_names),
            )
            conn.commit()
        finally:
            conn.close()

    def progressive_disclose(self, skill_name: str, level: str = "summary") -> str:
        """按级别返回内容 — 渐进式披露

        Args:
            skill_name: skill名称
            level: summary/detail/full

        Returns:
            对应级别的skill内容
        """
        manifest = self._manifests.get(skill_name)
        if not manifest:
            return ""

        if level == DisclosureLevel.FULL.value or level == "full":
            return manifest.render_full()
        elif level == DisclosureLevel.DETAIL.value or level == "detail":
            return manifest.render_detail()
        else:
            return manifest.render_summary()

    def search_skills(self, query: str, limit: int = 10) -> list[dict]:
        """FTS5全文搜索

        Args:
            query: 搜索关键词
            limit: 返回数量上限

        Returns:
            匹配的skill列表，每项包含name/description/category/score
        """
        results = []
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.execute(
                """SELECT name, description, category, tags, rank
                   FROM skill_search
                   WHERE skill_search MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            )
            for row in cursor.fetchall():
                results.append({
                    "name": row[0],
                    "description": row[1],
                    "category": row[2],
                    "tags": row[3].split(",") if row[3] else [],
                    "score": -row[4] if row[4] else 0.0,
                })
        except sqlite3.OperationalError:
            results = self._fallback_search(query, limit)
        finally:
            conn.close()
        return results

    def _fallback_search(self, query: str, limit: int) -> list[dict]:
        """FTS5不可用时的降级搜索"""
        results = []
        query_lower = query.lower()
        for name, entry in self._entries.items():
            score = 0.0
            if query_lower in name.lower():
                score += 2.0
            if query_lower in entry.description.lower():
                score += 1.0
            for tag in entry.tags:
                if query_lower in tag.lower():
                    score += 0.5
            if score > 0:
                results.append({
                    "name": entry.name,
                    "description": entry.description,
                    "category": entry.category,
                    "tags": entry.tags,
                    "score": score,
                })
        results.sort(key=lambda x: -x["score"])
        return results[:limit]

    def get_manifest(self, name: str) -> Optional[SkillManifest]:
        """获取完整manifest"""
        return self._manifests.get(name)

    def list_indexed(self) -> list[SkillIndexEntry]:
        """列出所有已索引skill"""
        return list(self._entries.values())

    def get_stats(self) -> dict:
        """获取索引统计"""
        categories: dict[str, int] = {}
        for entry in self._entries.values():
            categories[entry.category] = categories.get(entry.category, 0) + 1
        return {
            "total": len(self._entries),
            "categories": categories,
            "db_path": self._db_path,
        }

    def remove_skill(self, name: str) -> bool:
        """从索引中移除skill"""
        if name not in self._manifests:
            return False
        del self._manifests[name]
        del self._entries[name]
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("DELETE FROM skill_fts WHERE name = ?", (name,))
            conn.execute("DELETE FROM skill_search WHERE name = ?", (name,))
            conn.commit()
        finally:
            conn.close()
        return True


__all__ = ["SkillIndexer", "SkillIndexEntry"]