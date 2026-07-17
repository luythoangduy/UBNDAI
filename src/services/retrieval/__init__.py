"""Hybrid retrieval trên catalog TTHC. Owner: Dev A.

Port từ C2-App-108 — copy các file sau vào đây và đổi import (Sprint 0):
  - chroma_client.py, embeddings.py          # dense
  - bm25_retrieval.py                        # sparse
  - retrieval_common.py, retrieval.py        # RRF fusion, entrypoint
  - query_normalizer.py, query_expansion.py  # giữ pattern, viết lại few-shot cho domain TTHC
  - reranker.py                              # optional, bật sau khi có eval

Collection: ``tthc_procedures`` (env CHROMA_PERSIST_DIR). Mỗi chunk giữ metadata
procedure_id + section để trace citation (AGENTS.md §5).
"""
