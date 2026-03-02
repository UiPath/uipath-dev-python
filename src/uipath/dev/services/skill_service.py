"""Skill discovery and loading service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent / "skills"


@dataclass
class SkillInfo:
    """Metadata for a discovered skill."""

    id: str
    name: str
    description: str
    path: Path


class SkillService:
    """Discovers and loads built-in skills from the package."""

    def __init__(self) -> None:
        """Initialize the skill service."""
        self._skills_dir = SKILLS_DIR

    def list_skills(self) -> list[SkillInfo]:
        """Return one SkillInfo per reference file across all skill directories."""
        skills: list[SkillInfo] = []
        if not self._skills_dir.is_dir():
            return skills

        for child in sorted(self._skills_dir.iterdir()):
            if not child.is_dir():
                continue
            refs_dir = child / "references"
            if not refs_dir.is_dir():
                continue
            for md_file in sorted(refs_dir.rglob("*.md")):
                # Skip index/README files
                if md_file.stem.lower() in ("index", "readme"):
                    continue
                rel = md_file.relative_to(refs_dir)
                # ID: "uipath/authentication" or "uipath/evaluations/best-practices"
                skill_id = f"{child.name}/{rel.with_suffix('')}"
                # Human name from first # heading or filename
                name = self._extract_title(md_file) or rel.stem
                # Description from second line or first paragraph
                description = self._extract_description(md_file)
                skills.append(
                    SkillInfo(
                        id=skill_id, name=name, description=description, path=md_file
                    )
                )
        return skills

    def get_skill_content(self, skill_id: str) -> str:
        """Return the content of a skill (reference file)."""
        path = self._resolve_skill_file(skill_id)
        if not path.is_file():
            raise FileNotFoundError(f"Skill not found: {skill_id}")
        return path.read_text(encoding="utf-8")

    def get_skill_summary(self, skill_id: str) -> str:
        """Return a compact summary: title + description.

        This is injected into the system prompt instead of the full content,
        so the model can use ``read_reference`` to drill into details.
        Keeps it short — no section TOCs or reference file lists (those are
        appended once globally by the caller).
        """
        path = self._resolve_skill_file(skill_id)
        if not path.is_file():
            raise FileNotFoundError(f"Skill not found: {skill_id}")
        text = path.read_text(encoding="utf-8")

        title = ""
        first_paragraph = ""
        in_frontmatter = False
        past_title = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped == "---":
                in_frontmatter = not in_frontmatter
                continue
            if in_frontmatter:
                continue
            if (
                stripped.startswith("# ")
                and not stripped.startswith("##")
                and not title
            ):
                title = stripped
                past_title = True
            elif past_title and not first_paragraph and stripped:
                first_paragraph = stripped

        parts = [title or f"# {skill_id}"]
        if first_paragraph:
            parts.append(first_paragraph)
        parts.append(
            "\nUse `read_reference` with a filename to get full details on any topic."
        )
        return "\n".join(parts)

    def get_reference_files(self) -> list[str]:
        """Return a deduplicated list of all reference file names across skills."""
        seen: set[str] = set()
        result: list[str] = []
        if not self._skills_dir.is_dir():
            return result
        for child in sorted(self._skills_dir.iterdir()):
            refs_dir = child / "references"
            if not refs_dir.is_dir():
                continue
            for f in sorted(refs_dir.iterdir()):
                if f.is_file() and f.suffix == ".md" and f.name not in seen:
                    seen.add(f.name)
                    result.append(f.name)
        return result

    def get_reference(self, skill_id: str, ref_path: str) -> str:
        """Read a reference file relative to the skill's parent references dir."""
        # Skill ID is like "uipath/authentication" — base dir is "uipath"
        base_name = skill_id.split("/", 1)[0]
        if ".." in base_name or "/" in base_name or "\\" in base_name:
            raise PermissionError(f"Invalid skill ID: {skill_id}")
        refs_dir = (self._skills_dir / base_name / "references").resolve()
        ref = (refs_dir / ref_path).resolve()
        if not str(ref).startswith(str(refs_dir)):
            raise PermissionError(f"Path escapes references directory: {ref_path}")
        if not ref.is_file():
            raise FileNotFoundError(f"Reference not found: {ref_path}")
        return ref.read_text(encoding="utf-8")

    def _resolve_skill_file(self, skill_id: str) -> Path:
        """Resolve a skill ID like 'uipath/authentication' to its file path."""
        if ".." in skill_id:
            raise PermissionError(f"Invalid skill ID: {skill_id}")
        parts = skill_id.split("/", 1)
        if len(parts) != 2:
            raise FileNotFoundError(f"Invalid skill ID format: {skill_id}")
        base_name, ref_rel = parts
        return self._skills_dir / base_name / "references" / f"{ref_rel}.md"

    @staticmethod
    def _extract_title(path: Path) -> str:
        """Extract the first # heading from a markdown file."""
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("# ") and not stripped.startswith("##"):
                    return stripped[2:].strip()
        except Exception:
            pass
        return ""

    @staticmethod
    def _extract_description(path: Path) -> str:
        """Extract a short description from the first non-heading paragraph."""
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            for line in lines[1:]:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    return stripped[:120]
        except Exception:
            pass
        return ""
