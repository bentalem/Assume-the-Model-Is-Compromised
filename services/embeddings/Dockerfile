# The embedding model, served locally by Hugging Face text-embeddings-inference (TEI).
#
# Two stages. The first fetches the model at a pinned revision and checks every file against a
# pinned hash — the only moment anything here touches the network. The second is TEI with those
# files copied in, run from a local path with the hub disabled, so the running container needs no
# egress, holds no token, and cannot quietly pick up a different model.
#
# The model is fetched by this build rather than by TEI at startup for two reasons: the brief wants
# it offline, and TEI 1.5's own downloader cannot follow the relative redirects the Hugging Face hub
# now returns — it fails with "relative URL without a base". Measured, not assumed.
FROM python:3.12-slim-bookworm AS fetch
COPY services/embeddings/fetch_model.py /fetch_model.py
RUN python /fetch_model.py

FROM ghcr.io/huggingface/text-embeddings-inference:cpu-1.5
COPY --from=fetch /model /model
ENV HF_HUB_OFFLINE=1
# bge models pool on the [CLS] token; saying so avoids depending on a pooling config being read.
CMD ["--model-id", "/model", "--pooling", "cls", "--port", "80"]
