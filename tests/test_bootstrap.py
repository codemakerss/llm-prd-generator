from pathlib import Path

from llm_wiki_generator.bootstrap import (
    derive_index_db_path,
    initialize_wiki_location,
    inspect_bootstrap,
    normalize_wiki_root,
)


def test_bootstrap_status_is_uninitialized_without_env(tmp_path: Path) -> None:
    status = inspect_bootstrap(tmp_path)

    assert not status.env_exists
    assert not status.configured
    assert not status.initialized
    assert status.wiki_root is None
    assert "20-wiki/index.md" in status.missing_paths


def test_bootstrap_status_is_uninitialized_when_wiki_root_missing(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("LLM_MODEL=gpt-4.1-mini\n", encoding="utf-8")

    status = inspect_bootstrap(tmp_path)

    assert status.env_exists
    assert not status.configured
    assert not status.initialized
    assert status.wiki_root is None


def test_bootstrap_init_persists_custom_absolute_path(tmp_path: Path) -> None:
    chosen_root = tmp_path / "knowledge" / "vault"

    settings, created, env_path = initialize_wiki_location(tmp_path, chosen_root)

    assert env_path.exists()
    assert settings.wiki_root == chosen_root.resolve()
    assert settings.index_db == derive_index_db_path(chosen_root.resolve())
    assert created
    env_text = env_path.read_text(encoding="utf-8")
    assert f"WIKI_ROOT={chosen_root.resolve()}" in env_text
    assert f"WIKI_INDEX_DB={derive_index_db_path(chosen_root.resolve())}" in env_text
    assert (chosen_root / "20-wiki/index.md").exists()
    assert (chosen_root / "20-wiki/log.md").exists()


def test_bootstrap_init_normalizes_relative_path(tmp_path: Path) -> None:
    relative = "custom/wiki-vault"

    settings, _, _ = initialize_wiki_location(tmp_path, relative)

    assert settings.wiki_root == normalize_wiki_root(tmp_path, relative)
    assert settings.index_db == derive_index_db_path(settings.wiki_root)


def test_bootstrap_status_is_initialized_after_bootstrap_init(tmp_path: Path) -> None:
    initialize_wiki_location(tmp_path, tmp_path / "vault")

    status = inspect_bootstrap(tmp_path)

    assert status.env_exists
    assert status.configured
    assert status.initialized
    assert status.wiki_root == (tmp_path / "vault").resolve()
    assert status.index_db == (tmp_path / "vault" / "index.sqlite3").resolve()
    assert status.missing_paths == []
