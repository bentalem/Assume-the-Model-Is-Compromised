"""Fetch the embedding model at a pinned revision, and refuse anything that does not match.

Runs once, in the build stage of the embeddings image. The container that serves the model never
touches the network for it: TEI loads these files from a local path with the hub disabled.

Every file is pinned by SHA-256, not only the weights. A tokenizer or a pooling config that changed
under a fixed revision would change every vector without changing the model file, and a build that
could silently produce different embeddings is not reproducible in any sense that matters. A
mismatch fails the build.
"""

import hashlib
import os
import sys
import urllib.request

REPOSITORY = "BAAI/bge-small-en-v1.5"
REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
TARGET = "/model"

PINNED = {
    "config.json": "094f8e891b932f2000c92cfc663bac4c62069f5d8af5b5278c4306aef3084750",
    "tokenizer.json": "d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66",
    "tokenizer_config.json": "9261e7d79b44c8195c1cada2b453e55b00aeb81e907a6664974b4d7776172ab3",
    "special_tokens_map.json": "b6d346be366a7d1d48332dbc9fdf3bf8960b5d879522b7799ddba59e76237ee3",
    "vocab.txt": "07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3",
    "modules.json": "84e40c8e006c9b1d6c122e02cba9b02458120b5fb0c87b746c41e0207cf642cf",
    "sentence_bert_config.json": "84e39fda68ccbff05bfa723ae9c0e70e23e2ec373b76e0f8c6e71af72a693cbf",
    "config_sentence_transformers.json": "940d5f50db195fa6e5e6a4f122c095f77880de259d74b14a65779ed48bdd7c56",
    "1_Pooling/config.json": "d1caf60c96f5fba2157c0c26b76d80818fad6cf0b8eb5e73ec372ff9818eba5c",
    # The weights, in ONNX form. TEI's CPU image runs the ONNX runtime and will not start without
    # this file — the safetensors weights were fetched first and TEI refused them, which is why
    # this comment exists. This hash is also the one Hugging Face publishes for the LFS object.
    "onnx/model.onnx": "828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35",
}


def main() -> int:
    for name, expected in PINNED.items():
        destination = os.path.join(TARGET, name)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        url = f"https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/{name}"
        urllib.request.urlretrieve(url, destination)
        with open(destination, "rb") as handle:
            actual = hashlib.sha256(handle.read()).hexdigest()
        if actual != expected:
            print(f"FATAL: {name} is {actual}, pinned {expected}", file=sys.stderr)
            return 1
        print(f"ok  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
