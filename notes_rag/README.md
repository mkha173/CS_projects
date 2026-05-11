# notes-rag

Chat with your personal notes. Point it at a folder of `.md`, `.txt`, and `.pdf` files; it embeds the chunks locally, stores them in a persistent Chroma vector store, and answers your questions with Claude — with inline citations to the source files.

The "AI" part is two pieces: a local embedding model (sentence-transformers/all-MiniLM-L6-v2) for retrieval, and the Anthropic API for the actual answer. Everything else (chunking, the store, the CLI) is plain Python.

## Layout

```
.
├── cli.py              # CLI entry point: ingest / stats / ask / chat / reset
├── rag/
│   ├── ingest.py       # file loading + chunking
│   ├── store.py        # ChromaDB wrapper + embedding
│   └── chat.py         # Anthropic chat with retrieved context
├── requirements.txt
├── .env.example
└── sample_docs/
    └── linked_lists.md
```

The persistent index lives in `~/.rag-notes/chroma/` so it survives between runs. Delete that folder if you want to start fresh.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# then edit .env and paste your Anthropic API key
```

Get an API key at https://console.anthropic.com/.

## Use it

```bash
# Ingest a single file or a whole folder (recursive).
python cli.py ingest ./sample_docs

# See what's indexed.
python cli.py stats

# One-shot question.
python cli.py ask "what is a linked list good for?"

# Interactive chat (keeps history within the session).
python cli.py chat

# Wipe the index.
python cli.py reset
```

The first time you run `ingest` or `ask`, sentence-transformers will download the embedding model (~90 MB). After that it's local and offline.

## How it works

1. **Ingest.** Each file is read, split into ~800-character chunks with 100 chars of overlap (paragraph-aware so chunks don't break mid-sentence when possible), and each chunk gets a stable ID derived from its source path + chunk index — so re-ingesting the same file overwrites rather than duplicates.
2. **Embed + store.** Chunks are embedded with all-MiniLM-L6-v2 (384-dim, cosine), then upserted into a persistent Chroma collection.
3. **Retrieve.** Your question is embedded the same way, and the top-k chunks by cosine distance come back with their source filename.
4. **Answer.** The retrieved chunks are formatted into a CONTEXT block and sent to Claude with a system prompt that tells it to cite source filenames and refuse to answer outside the context. The CLI renders the answer plus a sources table.

## Things to extend

A short list of natural next steps if you want to grow this past a weekend project:

- **Hybrid retrieval.** Add BM25 (e.g. via `rank-bm25`) and merge results with the vector hits. Catches keyword queries that embeddings miss.
- **Reranking.** Pull top-20 from vector search, then rerank with a cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) before sending to Claude.
- **Better PDF parsing.** `pypdf` mangles tables and multi-column layouts. Swap in `unstructured` or `pymupdf` for serious documents.
- **Watch mode.** A file-watcher that re-ingests changed files automatically.
- **Web UI.** Wrap the same `Chat` class in a FastAPI route and put a small React or HTMX frontend on top.
- **Per-collection indexes.** Take `--collection work` / `--collection research` flags so you can keep work and personal notes separate.
- **Streaming answers.** Use `client.messages.stream(...)` instead of `.create(...)` and pipe tokens to the terminal as they arrive.

## Gotchas

- Make sure `ANTHROPIC_API_KEY` is set before running `ask` or `chat`. `python-dotenv` will pick up a local `.env` automatically.
- The default model is `claude-sonnet-4-5`; change it in `rag/chat.py` if your account doesn't have access.
- Embeddings are local but generation is not, so questions cost API tokens.
