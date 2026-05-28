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
                "scope": "project",
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


def test_skill_loader_prefers_workspace_skill_over_project_skill():
    tmp_dir = make_test_dir("skill-loader")
    try:
        project_skills = tmp_dir / "project" / "skills"
        workspace_skills = tmp_dir / "workspace" / "skills"
        project_skill = project_skills / "shared"
        workspace_skill = workspace_skills / "shared"
        project_skill.mkdir(parents=True)
        workspace_skill.mkdir(parents=True)
        (project_skill / "SKILL.md").write_text(
            """---
name: shared
description: Project version
---
Project body.
""",
            encoding="utf-8",
        )
        (workspace_skill / "SKILL.md").write_text(
            """---
name: shared
description: Workspace version
---
Workspace body.
""",
            encoding="utf-8",
        )

        loader = SkillLoader(project_skills, workspace_skills)

        assert loader.get_summaries() == [
            {
                "name": "shared",
                "description": "Workspace version",
                "path": str(workspace_skill / "SKILL.md"),
                "scope": "workspace",
            }
        ]
        assert "Workspace body." in loader.get_content("shared")
    finally:
        cleanup_test_dir(tmp_dir)


def test_skill_loader_uses_namespace_for_nested_pack_skills():
    tmp_dir = make_test_dir("skill-loader")
    try:
        skills_dir = tmp_dir / "skills"
        skill_dir = skills_dir / "superpowers" / "brainstorming"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            """---
name: brainstorming
description: Explore before building
---
Ask better questions.
""",
            encoding="utf-8",
        )

        loader = SkillLoader(skills_dir)

        assert loader.get_summaries() == [
            {
                "name": "superpowers:brainstorming",
                "description": "Explore before building",
                "path": str(skill_dir / "SKILL.md"),
                "scope": "project",
            }
        ]
        assert loader.get_content("superpowers:brainstorming") == (
            '<skill name="superpowers:brainstorming">\n'
            "Ask better questions.\n"
            "</skill>"
        )
    finally:
        cleanup_test_dir(tmp_dir)
