"""T7's definition of done: five packs load through the interface, and pack content is data.

The first half is an integration test against the real ``runtime_skills/`` directory -- not a
fixture, because a fixture would prove the registry works and say nothing about whether the packs
the pipeline will actually load are there and readable.

The second half is the part that is easy to let rot. "Content is data, not code" is true today
because nothing evaluates it; it stays true only if something fails when someone reaches for a
template engine to interpolate a pack. That is what the AST scan below is.
"""

import ast
import re
from pathlib import Path

import pytest

from adapters.local.skill_registry import DiskSkillRegistry
from interfaces import SkillRegistry

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "runtime_skills"

# The six LLM-facing steps of the pipeline: one pack each for outline (T15), scripting (T15),
# whole-video visual planning (T18B), scene authoring (T16), and (T18E) annotation authoring --
# run once a scene's blocks already have real content, so it can name a real item -- plus the
# shared voice pack the other five are interpolated alongside. Sorted, matching list_packs()'s
# own contract (DiskSkillRegistry.list_packs returns names alphabetically).
EXPECTED_PACKS = [
    "annotation-authoring",
    "house-style",
    "outline",
    "scene-authoring",
    "scripting",
    "visual-plan",
]

# The modules that stand between a pack file and a prompt. Nothing in this path may evaluate.
LOADING_MODULES = [
    REPO_ROOT / "adapters" / "skill_pack_format.py",
    REPO_ROOT / "adapters" / "local" / "skill_registry.py",
]

EVALUATORS = {"eval", "exec", "compile", "__import__"}
EVALUATING_IMPORTS = {"importlib", "jinja2", "runpy", "pickle", "marshal"}

# The T4 flag: target length is a parameter, so nothing may bake in 7 minutes or 15 segments.
# Segment count is derived from ``VideoJob.target_duration_ms``, and a pack asserting a number
# would override that silently -- the model believes the prompt over the schema.
HARDCODED_LENGTH = re.compile(r"\b(15|fifteen)\s+segments\b|\b(7|seven)[\s-]+minute", re.IGNORECASE)


@pytest.fixture
def shipped() -> SkillRegistry:
    return DiskSkillRegistry(SKILLS_ROOT)


# scene-authoring is at 1.5 (T18G: anchor_phrase on graph_diagram nodes/text_panel items/
# code_diff lines, title key_terms, icon_panel guidance). visual-plan is at 1.3 (T18G: icon_panel
# added to the block-choice table, plus a push against defaulting to text_panel/stat_callout).
# annotation-authoring is at 1.1 (T18G: adds CURSOR/CHECK/WARNING choice examples). Every other
# pack is still at its original 1.0. Keyed per-pack rather than one constant so a future version
# bump anywhere only has to update this map, not the reasoning around it.
LATEST_VERSION = {
    "annotation-authoring": "1.1",
    "house-style": "1.0",
    "outline": "1.0",
    "scene-authoring": "1.5",
    "scripting": "1.0",
    "visual-plan": "1.3",
}


async def test_the_four_packs_load_through_the_interface(shipped: SkillRegistry) -> None:
    """The DoD, stated once. Through ``SkillRegistry``, never by reading the directory."""
    assert await shipped.list_packs() == EXPECTED_PACKS

    for name in EXPECTED_PACKS:
        pack = await shipped.load(name)
        assert pack.name == name
        assert pack.version == LATEST_VERSION[name]
        assert len(pack.content.split()) > 100, f"{name} is too thin to be worth loading"


@pytest.mark.parametrize("name", EXPECTED_PACKS)
async def test_every_pack_is_at_a_version_the_registry_can_find(
    shipped: SkillRegistry, name: str
) -> None:
    versions = await shipped.versions(name)
    assert versions[0] == LATEST_VERSION[name], "versions() promises newest first"
    assert "1.0" in versions


@pytest.mark.parametrize("name", EXPECTED_PACKS)
async def test_every_pack_carries_its_provenance(shipped: SkillRegistry, name: str) -> None:
    """Metadata is what makes a version reversible: without it, ``2.0`` is an unexplained diff."""
    metadata = (await shipped.load(name)).metadata

    assert metadata["author"]
    assert metadata["updated"]
    assert isinstance(metadata["updated"], str)


@pytest.mark.parametrize("name", EXPECTED_PACKS)
async def test_no_pack_hardcodes_the_video_length(shipped: SkillRegistry, name: str) -> None:
    """Flagged at T4 and true of prompts as much as of code.

    ``VideoJob.target_duration_ms`` is the only place a length lives; a ten-minute request
    derives about 21 segments on its own. A pack that says "fifteen segments" is a constant the
    model will obey over the schema, and it would be invisible until someone asked for a
    different length.
    """
    content = (await shipped.load(name)).content

    assert not HARDCODED_LENGTH.search(content), f"{name} bakes in a video length"


# --- Content is data, not code ---------------------------------------------------------------


def names_used(module: Path) -> set[str]:
    """Every bare name referenced in ``module``, via the AST rather than a text search.

    The standing gotcha: the project's boundary greps are plain-text searches, and a docstring
    mentioning ``eval`` is not a call to it. This module's own docstring is the proof.
    """
    tree = ast.parse(module.read_text(encoding="utf-8"))
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}


def import_roots(module: Path) -> set[str]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("module", LOADING_MODULES, ids=lambda p: p.name)
def test_nothing_on_the_loading_path_can_evaluate_a_pack(module: Path) -> None:
    """The load-bearing half of the DoD, made mechanical.

    A pack is interpolated into a prompt and nothing else. The failure this guards against is
    not malice -- it is someone reaching for Jinja to substitute a variable into a pack, which
    hands pack text a template engine with access to Python objects. Templates belong in
    ``rendering/``, where the output is markup nobody executes.
    """
    assert not names_used(module) & EVALUATORS, module.name
    assert not import_roots(module) & EVALUATING_IMPORTS, module.name


async def test_pack_content_is_returned_verbatim(tmp_path: Path) -> None:
    """Text that would be meaningful to a template engine or an interpreter comes back as text.

    The direct statement of the rule: the registry is not a template renderer, and it is not one
    for content that looks like it wants to be rendered either.
    """
    hostile = "{{ 7 * 7 }} and ${HOME} and __import__('os').getcwd()"
    (tmp_path / "outline").mkdir()
    (tmp_path / "outline" / "1.0.md").write_text(f"---\nauthor: t\n---\n\n{hostile}\n", "utf-8")

    pack = await DiskSkillRegistry(tmp_path).load("outline")

    assert pack.content == hostile
