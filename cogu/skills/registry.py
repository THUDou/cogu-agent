import os
import shutil
import tempfile
import urllib.request
import urllib.error
import urllib.parse
import zipfile
import tarfile
from pathlib import Path
from typing import Optional

from cogu.skills.spec import SkillSpec


DEFAULT_USER_SKILLS_DIR = "~/.cogu/skills"
DEFAULT_PROJECT_SKILLS_DIR = ".cogu/skills"


def _is_url(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://") or source.startswith("file://")


def _find_skill_md(root: Path) -> Optional[Path]:
    for skill_md in root.rglob("SKILL.md"):
        return skill_md
    return None


def _download_extract(url: str, dest: Path) -> bool:
    if url.startswith("file://"):
        from urllib.request import url2pathname
        try:
            parsed = urllib.parse.urlparse(url)
            src = Path(url2pathname(parsed.path))
        except Exception:
            src = Path(url.replace("file://", "", 1))
        if not src.exists():
            return False
        data = src.read_bytes()
    else:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "cogu-agent"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
        except urllib.error.URLError:
            return False

    dest.parent.mkdir(parents=True, exist_ok=True)

    if url.endswith(".zip") or "github.com" in url and "/archive/" in url:
        tmp = Path(tempfile.mktemp(suffix=".zip"))
        tmp.write_bytes(data)
        try:
            with zipfile.ZipFile(tmp, "r") as zf:
                members = zf.namelist()
                if members and "/" in members[0]:
                    prefix = members[0].split("/")[0]
                    zf.extractall(dest.parent)
                    extracted = dest.parent / prefix
                    if extracted.is_dir() and extracted != dest:
                        shutil.rmtree(str(dest), ignore_errors=True)
                        shutil.move(str(extracted), str(dest))
                else:
                    zf.extractall(dest)
        finally:
            tmp.unlink(missing_ok=True)
    elif url.endswith(".tar.gz") or url.endswith(".tgz"):
        tmp = Path(tempfile.mktemp(suffix=".tar.gz"))
        tmp.write_bytes(data)
        try:
            with tarfile.open(tmp, "r:gz") as tf:
                members = tf.getnames()
                if members and "/" in members[0]:
                    prefix = members[0].split("/")[0]
                    tf.extractall(dest.parent, filter="data")
                    extracted = dest.parent / prefix
                    if extracted.is_dir() and extracted != dest:
                        shutil.rmtree(str(dest), ignore_errors=True)
                        shutil.move(str(extracted), str(dest))
                else:
                    tf.extractall(dest, filter="data")
        finally:
            tmp.unlink(missing_ok=True)
    else:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "SKILL.md").write_bytes(data)

    return True


class SkillRegistry:
    def __init__(self, workspace: str = ""):
        self._skills: dict[str, SkillSpec] = {}
        self._workspace = workspace
        self._search_paths: list[str] = []
        self._refresh_search_paths()

    @property
    def user_skills_dir(self) -> str:
        return os.path.expanduser(DEFAULT_USER_SKILLS_DIR)

    @property
    def project_skills_dir(self) -> str:
        if self._workspace:
            return os.path.join(self._workspace, DEFAULT_PROJECT_SKILLS_DIR)
        return ""

    def _refresh_search_paths(self):
        self._search_paths = []
        if os.path.isdir(self.user_skills_dir):
            self._search_paths.append(self.user_skills_dir)
        if self._workspace:
            pdir = self.project_skills_dir
            if os.path.isdir(pdir):
                self._search_paths.append(pdir)

    def discover(self, skill_dir: str = "") -> list[SkillSpec]:
        dirs_to_scan = [skill_dir] if skill_dir else self._search_paths
        discovered = []
        for base_dir in dirs_to_scan:
            base = Path(base_dir)
            if not base.is_dir():
                continue
            for skill_md in base.rglob("SKILL.md"):
                spec = SkillSpec.from_markdown(str(skill_md))
                if spec and spec.name:
                    self._skills[spec.name] = spec
                    discovered.append(spec)
        return discovered

    def load(self, name: str) -> Optional[SkillSpec]:
        if name in self._skills:
            return self._skills[name]
        self.discover()
        return self._skills.get(name)

    def register(self, spec: SkillSpec):
        self._skills[spec.name] = spec

    def unregister(self, name: str) -> bool:
        return self._skills.pop(name, None) is not None

    def list_all(self) -> list[str]:
        if not self._skills:
            self.discover()
        return sorted(self._skills.keys())

    def list_loaded(self) -> list[SkillSpec]:
        return list(self._skills.values())

    def search(self, query: str) -> list[SkillSpec]:
        results = []
        query_lower = query.lower()
        for spec in self._skills.values():
            if query_lower in spec.name.lower() or query_lower in spec.description.lower():
                results.append(spec)
        return results

    def find_by_tool(self, tool_name: str) -> list[SkillSpec]:
        results = []
        for spec in self._skills.values():
            if tool_name in spec.tools:
                results.append(spec)
        return results

    def install_skill(self, source: str, level: str = "user") -> Optional[SkillSpec]:
        if _is_url(source):
            return self._install_from_url(source, level)
        return self._install_from_local(source, level)

    def _install_from_local(self, source_dir: str, level: str = "user") -> Optional[SkillSpec]:
        src = Path(source_dir).resolve()
        if not src.is_dir():
            return None
        skill_md = src / "SKILL.md"
        if not skill_md.exists():
            skill_md = _find_skill_md(src)
        if not skill_md:
            return None
        spec = SkillSpec.from_markdown(str(skill_md))
        if not spec:
            return None
        target_root = Path(self.user_skills_dir).resolve() if level == "user" else Path(self.project_skills_dir).resolve()
        if str(src).startswith(str(target_root)):
            self._skills[spec.name] = spec
            return spec
        dest_dir = self._copy_skill(spec, src, level)
        if dest_dir:
            spec = SkillSpec.from_markdown(str(dest_dir / "SKILL.md"))
        if spec:
            self._skills[spec.name] = spec
        return spec

    def _install_from_url(self, url: str, level: str = "user") -> Optional[SkillSpec]:
        tmp_root = Path(tempfile.mkdtemp(prefix="cogu_skill_"))
        try:
            dest = tmp_root / "skill"
            if not _download_extract(url, dest):
                return None
            skill_md = _find_skill_md(dest)
            if not skill_md:
                skill_md = _find_skill_md(tmp_root)
            if not skill_md:
                return None
            spec = SkillSpec.from_markdown(str(skill_md))
            if not spec:
                return None
            skill_src_dir = skill_md.parent
            dest_dir = self._copy_skill(spec, skill_src_dir, level)
            if dest_dir:
                spec = SkillSpec.from_markdown(str(dest_dir / "SKILL.md"))
            if spec:
                self._skills[spec.name] = spec
            return spec
        finally:
            shutil.rmtree(str(tmp_root), ignore_errors=True)

    def _copy_skill(self, spec: SkillSpec, src_dir: Path, level: str = "user") -> Optional[Path]:
        target_root = Path(self.user_skills_dir if level == "user" else self.project_skills_dir)
        if not target_root or not str(target_root):
            return None
        target_root.mkdir(parents=True, exist_ok=True)
        dest_dir = target_root / spec.name
        if dest_dir.exists():
            shutil.rmtree(str(dest_dir), ignore_errors=True)
        shutil.copytree(str(src_dir), str(dest_dir))
        return dest_dir

    def uninstall_skill(self, name: str) -> bool:
        spec = self._skills.pop(name, None)
        if spec and spec.home_dir:
            skill_dir = Path(spec.home_dir)
            if skill_dir.is_dir() and skill_dir.name == name:
                shutil.rmtree(str(skill_dir), ignore_errors=True)
            return True
        target = Path(self.user_skills_dir) / name
        if target.is_dir():
            shutil.rmtree(str(target), ignore_errors=True)
            return True
        return False

    def build_context(self, skill_names: list[str], max_per_skill: int = 4000) -> str:
        parts = []
        for name in skill_names:
            spec = self.load(name)
            if spec:
                parts.append(spec.render_context(max_per_skill))
        return "\n\n---\n\n".join(parts) if parts else ""

    def size(self) -> int:
        return len(self._skills)
