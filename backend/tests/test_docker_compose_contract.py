from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def _compose_services() -> dict:
    payload = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    return payload["services"]


def test_backend_container_mounts_dataset_directory_for_startup_import():
    backend = _compose_services()["backend"]

    assert "./data:/app/data:ro" in backend.get("volumes", [])


def test_backend_container_receives_llm_environment_from_project_env():
    backend = _compose_services()["backend"]
    environment = backend["environment"]

    assert environment["OPENAI_API_KEY"] == "${OPENAI_API_KEY:-}"
    assert environment["OPENAI_BASE_URL"] == "${OPENAI_BASE_URL:-}"
    assert environment["OPENAI_FALLBACK_BASE_URLS"] == "${OPENAI_FALLBACK_BASE_URLS:-}"
    assert environment["LLM_MODEL"] == "${LLM_MODEL:-}"
    assert environment["LLM_FALLBACK_MODELS"] == "${LLM_FALLBACK_MODELS:-}"
