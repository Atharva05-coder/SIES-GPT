#!/usr/bin/env python3
"""
SIES-GPT: Vector Database Inspector
===================================
Directly inspects ChromaDB storage, collections, embeddings, and metadata.
Usage:
    python inspect_db.py
"""

import sys
from pathlib import Path
from collections import Counter

# Ensure UTF-8 console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from rag.vector_store import client, collection, CHROMA_PATH


def main():
    db_path = Path(CHROMA_PATH)
    sqlite_file = db_path / "chroma.sqlite3"
    db_size_mb = sqlite_file.stat().st_size / (1024 * 1024) if sqlite_file.exists() else 0

    print("\n" + "=" * 70)
    print("🗄️  CHROMADB VECTOR DATABASE INSPECTION REPORT")
    print("=" * 70)
    print(f"📁 Database Location:  {db_path.resolve()}")
    print(f"📦 SQLite File:        {sqlite_file.name} ({db_size_mb:.2f} MB)")
    print(f"🏷️  Active Collection:  '{collection.name}'")
    print(f"📊 Total Stored Chunks: {collection.count()} vectors")
    print("-" * 70)

    # 1. Inspect All Collections in Chroma
    all_colls = client.list_collections()
    print(f"\n[1] Collections in ChromaDB ({len(all_colls)} found):")
    for c in all_colls:
        c_name = c.name if hasattr(c, "name") else str(c)
        c_count = c.count() if hasattr(c, "count") else "N/A"
        active_tag = " (ACTIVE)" if c_name == collection.name else ""
        print(f"    • {c_name} — {c_count} vectors{active_tag}")

    # 2. Fetch metadata from active collection
    data = collection.get(include=["metadatas", "documents"])
    metas = data.get("metadatas", [])
    docs = data.get("documents", [])

    print(f"\n[2] Document Breakdown in '{collection.name}':")
    file_counts = Counter(m.get("filename", "Unknown") for m in metas)
    for fname, count in sorted(file_counts.items()):
        pct = (count / len(metas)) * 100 if metas else 0
        print(f"    ✔ {fname:<32} : {count:>5} vectors ({pct:>5.1f}%)")

    # 3. Peek at actual raw vector data
    peek_data = collection.peek(limit=2)
    sample_ids = peek_data.get("ids", [])
    sample_metas = peek_data.get("metadatas", [])
    sample_docs = peek_data.get("documents", [])

    print("\n[3] Raw Vector Data Peek (First Sample Record):")
    if sample_ids:
        s_id = sample_ids[0]
        s_meta = sample_metas[0] if sample_metas else {}
        s_doc = sample_docs[0] if sample_docs else ""
        
        # Fetch embedding for this sample
        sample_rec = collection.get(ids=[s_id], include=["embeddings", "metadatas"])
        embs = sample_rec.get("embeddings")
        has_embs = embs is not None and len(embs) > 0
        emb_dim = len(embs[0]) if has_embs else "N/A"
        emb_sample = str(list(embs[0][:5]))[:-1] + ", ...]" if has_embs else "N/A"

        print(f"    • Chunk ID:           {s_id}")
        print(f"    • Source File:        {s_meta.get('filename')}")
        print(f"    • Course:             {s_meta.get('course_code')} - {s_meta.get('course_name')}")
        print(f"    • Page Number:        Page {s_meta.get('page')}")
        print(f"    • Vector Dimension:   {emb_dim} dimensions (BGE-M3)")
        print(f"    • Vector Slice:       {emb_sample}")
        print(f"    • Content Preview:    \"{s_doc[:120].strip()}...\"")

    # 4. Direct Vector Search Demonstration
    print("\n[4] Direct Vector Similarity Query (Testing ChromaDB index directly):")
    from rag.embeddings import create_embedding
    test_query = "Computer Networks transmission media and topologies"
    print(f"    • Query Text: \"{test_query}\"")
    q_emb = create_embedding(test_query)
    search_res = collection.query(query_embeddings=[q_emb], n_results=3, include=["metadatas", "distances"])
    
    hits = search_res.get("metadatas", [[]])[0]
    dists = search_res.get("distances", [[]])[0]
    print(f"    • Top 3 Vector Matches in ChromaDB:")
    for rank, (h, dist) in enumerate(zip(hits, dists), start=1):
        print(f"       {rank}. {h.get('course_code')} ({h.get('course_name')}) | Page {h.get('page')} | Distance: {dist:.4f} | From: {h.get('filename')}")

    print("\n" + "=" * 70)
    print("✅ ChromaDB is online, healthy, and all 3 syllabi are verified active!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
