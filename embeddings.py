"""
Lightweight ONNX-based sentence embeddings.

Replaces sentence-transformers + PyTorch (~5GB) with
onnxruntime + tokenizers (~200MB total).

Produces identical 384-dim embeddings for all-MiniLM-L6-v2.
"""

import os
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer
from huggingface_hub import hf_hub_download


MODEL_REPO = "sentence-transformers/all-MiniLM-L6-v2"


class LightEmbeddingModel:
    """Drop-in replacement for SentenceTransformer.encode()."""

    def __init__(self, model_name: str = MODEL_REPO, cache_dir: str = None):
        cache_dir = cache_dir or os.environ.get(
            "HF_HOME", os.path.expanduser("~/.cache/huggingface")
        )

        # Download ONNX model and tokenizer from HuggingFace
        print(f"📦 Loading ONNX model: {model_name}")
        onnx_path = hf_hub_download(
            model_name, "onnx/model.onnx", cache_dir=cache_dir
        )
        tokenizer_path = hf_hub_download(
            model_name, "tokenizer.json", cache_dir=cache_dir
        )

        # Initialize ONNX Runtime session (CPU)
        self.session = ort.InferenceSession(
            onnx_path, providers=["CPUExecutionProvider"]
        )

        # Initialize fast tokenizer
        self.tokenizer = Tokenizer.from_file(tokenizer_path)
        self.tokenizer.enable_padding()
        self.tokenizer.enable_truncation(max_length=256)

        print("✅ ONNX embedding model ready")

    def encode(self, texts) -> np.ndarray:
        """Encode texts to 384-dim normalized embeddings.

        Compatible with SentenceTransformer.encode() output.
        """
        if isinstance(texts, str):
            texts = [texts]

        encodings = self.tokenizer.encode_batch(texts)

        input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
        attention_mask = np.array(
            [e.attention_mask for e in encodings], dtype=np.int64
        )
        token_type_ids = np.zeros_like(input_ids, dtype=np.int64)

        # Run ONNX inference
        outputs = self.session.run(
            None,
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids,
            },
        )

        # Mean pooling (same as sentence-transformers default)
        token_embeddings = outputs[0]  # (batch, seq_len, 384)
        mask_expanded = attention_mask[:, :, np.newaxis].astype(np.float32)
        summed = np.sum(token_embeddings * mask_expanded, axis=1)
        counts = np.clip(np.sum(mask_expanded, axis=1), a_min=1e-9, a_max=None)
        embeddings = summed / counts

        # L2 normalize
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / np.clip(norms, a_min=1e-9, a_max=None)

        return embeddings.astype(np.float32)
