import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.conftest import cleanup_test_dir, make_test_dir
from agent.core.skill_loader import SkillLoader


def test_skill_loader_reads_frontmatter_and_body():
    tmp_dir = make_test_dir("skill-loader")
    try:
        skills_dir = tmp_dir / "skills"
        skill_dir = skills_dir / "pdf"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            """---
name: pdf
description: Process PDF files
tags: docs, files
---
Step 1: inspect pages
Step 2: extract content
""",
            encoding="utf-8",
        )

        loader = SkillLoader(skills_dir)

        summaries = loader.get_summaries()
        assert summaries == [
            {
                "name": "pdf",
                "description": "Process PDF files",
                "tags": "docs, files",
                "path": str(skill_dir / "SKILL.md"),
            }
        ]
        assert loader.get_content("pdf") == (
            '<skill name="pdf">\n'
            "Step 1: inspect pages\n"
            "Step 2: extract content\n"
            "</skill>"
        )
    finally:
        cleanup_test_dir(tmp_dir)


def test_skill_loader_reports_available_names_for_unknown_skill():
    tmp_dir = make_test_dir("skill-loader")
    try:
        skills_dir = tmp_dir / "skills"
        skill_dir = skills_dir / "review"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            """---
name: review
description: Review code changes
---
Review carefully.
""",
            encoding="utf-8",
        )

        loader = SkillLoader(skills_dir)

        missing = loader.get_content("pdf")

        assert "Unknown skill 'pdf'" in missing
        assert "review" in missing
    finally:
        cleanup_test_dir(tmp_dir)
