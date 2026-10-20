;# SIES GPT — V3 ingestion update

## What this fixes

1. `CEC503` is no longer assigned to pages just because `CEC503` appears in a prerequisite.
2. Page 19 remains the start of course-content processing.
3. Computer Network is correctly detected at page 26.
4. The old Chroma collection is NOT reused.
5. New collection: `sies_gst_rag_v3`.
6. New collection uses `nomic-embed-text:latest` consistently.
7. Duplicate IDs are prevented with a global chunk index.
8. `chunk_documents()` is available, so the earlier `ImportError` is fixed.
9. Complete syllabus retrieval is deterministic and course-filtered.

## Files to replace

Copy these files into your backend:

- `ingest.py` → `backend/ingest.py`
- `chunker.py` → `backend/rag/chunker.py`
- `vector_store.py` → `backend/rag/vector_store.py`
- `retriever.py` → `backend/rag/retriever.py`
- `test_rag.py` → `backend/test_rag.py`

## Important

Do NOT delete your old `chroma_db` folder yet.

The new code uses:

`sies_gst_rag_v3`

so the old collection remains available as a backup.

## Run order

Open PowerShell:

```powershell
cd C:\Users\athar\Downloads\SIES-GPT\backend
.venv\Scripts\Activate.ps1
```

Make sure Ollama is running and the embedding model exists:

```powershell
ollama list
```

You should have:

```text
nomic-embed-text:latest
```

If necessary:

```powershell
ollama pull nomic-embed-text:latest
```

Then run:

```powershell
python ingest.py
```

DO NOT run `test_rag.py` until ingestion ends with:

```text
INGESTION SUCCESSFUL
Collection: sies_gst_rag_v3
```

## What to check during ingestion

The important course-header output should include:

```text
Page 19: CEC501 - Theoretical Computer Science
Page 22: CEC502 - Software Engineering
Page 26: CEC503 - Computer Network
```

Later, page 107 must say:

```text
Page 107: CEC602 - Cryptography and Network Security
```

NOT:

```text
Page 107: CEC503 - Computer Network
```

Page 133 must say:

```text
Page 133: CEPEC6013 - Digital Forensics
```

NOT CEC503.

Page 167 should be a lab/non-theory boundary if the catalog identifies that page as a lab.

## Then test

```powershell
python test_rag.py
```

Ask:

```text
Give me the complete Computer Network syllabus
```

The retrieved Computer Network chunks should be from the CEC503 course only.

For Computer Network, the detailed syllabus begins on PDF page 26 and the module content continues through pages 27–28.

## If ingestion fails with embedding dimension

The new code explicitly expects:

```text
Embedding dimension: 768
```

If it reports 3072 or another value, stop and show the complete error.

Do not change the collection back to the old one.

## After this passes

Only after `test_rag.py` gives correct results should the FastAPI/backend be switched from the old Chroma collection to:

```text
sies_gst_rag_v3
```
