import os

from infra_ingest.config import find_vault_root, load_environment, resolve_env_path


def test_resolve_env_path_relative_to_base_dir(tmp_path):
    assert resolve_env_path(".env.test", tmp_path) == tmp_path / ".env.test"


def test_load_environment_uses_python_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_MODEL=test-model\nQUOTED='hello there'\n", encoding="utf-8")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("QUOTED", raising=False)

    assert load_environment(env_file) is True
    assert os.environ["LLM_MODEL"] == "test-model"
    assert os.environ["QUOTED"] == "hello there"


def test_find_vault_root_walks_up_to_obsidian_folder(tmp_path):
    vault = tmp_path / "vault"
    nested = vault / "a" / "b"
    (vault / ".obsidian").mkdir(parents=True)
    nested.mkdir(parents=True)

    assert find_vault_root(nested) == str(vault)
