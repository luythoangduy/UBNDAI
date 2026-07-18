from types import SimpleNamespace

import pytest

from src.services.retrieval import embeddings


class _Encoded:
    def __init__(self, values: list[list[float]]) -> None:
        self.values = values

    def tolist(self) -> list[list[float]]:
        return self.values


class _InferenceClient:
    def __init__(self, **kwargs: object) -> None:
        self.init_kwargs = kwargs
        self.calls: list[dict[str, object]] = []

    def feature_extraction(self, texts: list[str], **kwargs: object) -> _Encoded:
        self.calls.append({"texts": texts, **kwargs})
        return _Encoded([[1.0, 0.0] for _ in texts])


def test_huggingface_embedding_uses_normalized_remote_bge_m3(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_valid_test_token")
    monkeypatch.setattr(embeddings, "InferenceClient", _InferenceClient)
    monkeypatch.setattr(
        embeddings,
        "settings",
        SimpleNamespace(
            huggingface_inference_provider="hf-inference",
            huggingface_inference_timeout_s=60.0,
            huggingface_embedding_model_name="BAAI/bge-m3",
        ),
    )

    model = embeddings.get_embedding_model("huggingface")
    result = model.embed_documents(["khai sinh", "cấp bản sao"])

    assert result == [[1.0, 0.0], [1.0, 0.0]]
    assert model.client.init_kwargs == {
        "provider": "hf-inference",
        "api_key": "hf_valid_test_token",
        "timeout": 60.0,
    }
    assert model.client.calls == [
        {
            "texts": ["khai sinh", "cấp bản sao"],
            "model": "BAAI/bge-m3",
            "normalize": True,
            "truncate": True,
        }
    ]


def test_huggingface_embedding_requires_token(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_API_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="HF_TOKEN"):
        embeddings.HuggingFaceInferenceEmbeddingModel("BAAI/bge-m3")
