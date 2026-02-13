import os
from huggingface_hub import hf_hub_download

# Download ONNX model and tokenizer
print("📦 Downloading ONNX model for all-MiniLM-L6-v2...")
hf_hub_download('sentence-transformers/all-MiniLM-L6-v2', 'onnx/model.onnx')
hf_hub_download('sentence-transformers/all-MiniLM-L6-v2', 'tokenizer.json')
print("✅ Download complete.")
