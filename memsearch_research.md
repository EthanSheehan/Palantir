---
tags: [grid_sentinel]
---
# memsearch MCP Plugin Research Report

**Repository:** https://github.com/zilliztech/memsearch
**Current Version:** 0.1.19 (released 2026-03-23)
**Last Commit:** 2026-03-25
**GitHub Stars:** 1,032
**Forks:** 94
**License:** MIT

---

## 1. What It Actually Does

**memsearch** is a **markdown-first semantic memory system** for AI agents. It stores agent memories as plain `.md` files, automatically indexes them into a vector database, and enables semantic search across those memories.

### Core Architecture

```
Markdown files → Chunker → Embedder → Milvus Vector Store → Search + Retrieval
```

- **Input:** Markdown files (any directory)
- **Processing:** Automatically chunks by heading/paragraph, deduplicates by content hash
- **Storage:** Vector embeddings in Milvus (with BM25 full-text index)
- **Output:** Hybrid search results (dense vector + keyword, RRF reranked)

### Key Workflow

1. **Index**: Scans markdown directories, chunks content, computes embeddings, stores in Milvus
2. **Search**: Semantic search (query embedding + BM25) with hybrid reranking
3. **Watch**: File watcher auto-indexes on changes, deletes stale chunks when files removed
4. **Compact**: Summarizes indexed chunks into condensed markdown via LLM

### Integration with Claude Code

Ships with a **Claude Code plugin** that:
- Auto-summarizes sessions to daily markdown files
- Injects recent memories at session start
- Provides a `memory-recall` skill for intelligent retrieval in subagents
- Runs a background `memsearch watch` process to keep index in sync
- Uses 4 lifecycle hooks: SessionStart, UserPromptSubmit, Stop, SessionEnd

---

## 2. Technical Implementation

### Embedding Models & Providers

memsearch supports **6 embedding providers**:

| Provider | Default Model | API Key? | Hardware | Installation |
|----------|---------------|----------|----------|--------------|
| **ONNX** ⭐ | `bge-m3-onnx-int8` | No | CPU only | `pip install memsearch[onnx]` |
| **OpenAI** | `text-embedding-3-small` | Yes | API | `pip install memsearch` (default) |
| **Google Gemini** | `gemini-embedding-001` | Yes | API | `pip install memsearch[google]` |
| **Voyage AI** | `voyage-3-lite` | Yes | API | `pip install memsearch[voyage]` |
| **Ollama** (local) | `nomic-embed-text` | No | Local | `pip install memsearch[ollama]` |
| **Local** (sentence-transformers) | `all-MiniLM-L6-v2` | No | Local | `pip install memsearch[local]` |

**ONNX Details:**
- Uses `onnxruntime` (no GPU required, runs on CPU)
- Downloads `gpahal/bge-m3-onnx-int8` from HuggingFace Hub (~558 MB)
- Int8 quantization for 4x smaller model size
- **Quality:** ~1% lower than OpenAI text-embedding-3-small (per their benchmarks)
- **Default for Claude Code plugin** — zero-config, no API key

### Vector Storage: Milvus

memsearch uses **Milvus** (open-source vector database) with three deployment modes:

| Mode | URI | Best For | Availability |
|------|-----|----------|--------------|
| **Milvus Lite** (default) | `~/.memsearch/milvus.db` | Personal use, dev | ⚠️ **Not available on Windows** |
| **Milvus Server** | `http://localhost:19530` | Multi-agent, teams | Docker required |
| **Zilliz Cloud** (managed) | `https://in03-xxx.api.gcp-us-west1.zillizcloud.com` | Production, zero-ops | Free tier available |

**Collection Structure (Milvus):**
- **Primary Key:** `chunk_hash` (SHA-256 of chunk content)
- **Fields:**
  - `embedding` (dense vector, dimension depends on provider)
  - `content` (text, with analyzer enabled for BM25)
  - `sparse_vector` (auto-generated BM25 from content)
  - `source` (file path)
  - `heading`, `heading_level`, `start_line`, `end_line` (metadata)
- **Indexes:** FLOAT_VECTOR (COSINE metric) + SPARSE_FLOAT_VECTOR (BM25)

**Search Strategy:** Hybrid search
- Dense vector search (semantic similarity)
- BM25 full-text search (keyword matching)
- RRF (Reciprocal Rank Fusion) reranking with k=60

### Chunking Strategy

- **Heading-based**: Chunks align with markdown structure
- **Paragraph-based**: Falls back to paragraphs if headings too large
- **Configurable:** `max_chunk_size=1500` (default), `overlap_lines=2`
- **Deduplication:** Content hash (SHA-256) + composite chunk ID
  - Unchanged content **never re-embedded** (saves API costs, faster indexing)
  - Format: `{source}::{start_line}::{end_line}::{content_hash}::{model}`

### Storage Format: Git-Friendly Markdown

**Source of truth:** Plain `.md` files in any directory
```
./memory/
├── 2026-02-09.md
├── 2026-02-10.md
└── NOTES.md
```

**Vector store:** Derived index (rebuilds anytime)
- `~/.memsearch/milvus.db` (Milvus Lite, local, SQLite-based)
- Or remote Milvus/Zilliz Cloud

**Config:** TOML files (supports global + project-level)
```toml
# ~/.memsearch/config.toml (global)
[embedding]
provider = "onnx"
model = "gpahal/bge-m3-onnx-int8"

[milvus]
uri = "~/.memsearch/milvus.db"

# .memsearch.toml (per-project, overrides global)
[milvus]
uri = "http://localhost:19530"
```

---

## 3. Git-Friendly / Markdown-Based

✅ **Fully git-friendly:**
- **Markdown is the source of truth** — just `.md` files
- Vector store is a **derived index**, completely disposable
- Can rebuild entire index anytime: `memsearch index --force`
- Markdown files naturally track via `git`
- `.memsearch/` directory (config + local DB) can be `.gitignore`d if using remote Milvus

**OpenClaw-style daily logs:**
```markdown
## {date}

### {heading}
Content of memory...

## 2026-02-10

### Session: Built auth module
- Added JWT token validation
- Implemented refresh token rotation
- Tested with 500+ accounts

### Decision: Redis over Memcached
- Selected for atomic operations
- Better memory efficiency
```

---

## 4. Token Overhead (If Any)

**No token overhead in normal operation:**
- Embedding happens **once at index time**, stored in vector DB
- Search queries: only the query is embedded (1 API call for non-ONNX providers)
- Transcript parsing happens **locally** (no LLM needed)

**Optional LLM cost (Compact feature):**
- `memsearch compact` uses an LLM to summarize chunks → markdown
- This is **opt-in**, not automatic
- Uses Haiku (cheapest) by default for summarization

**Claude Code plugin token usage:**
- SessionStart: injects recent daily logs (cached in `additionalContext`)
- UserPromptSubmit: lightweight hint (fixed string "[memsearch] Memory available")
- Stop: summarizes last turn using Haiku (via `claude -p --model haiku`)
- SessionEnd: cleanup only

---

## 5. Multiple User/Worker Support

✅ **Fully supported via Milvus collections:**

**Isolation by collection name:**
```python
# Agent 1's memory
mem1 = MemSearch(paths=["./memory/agent1"], collection="agent1_memory")

# Agent 2's memory (same Milvus server)
mem2 = MemSearch(paths=["./memory/agent2"], collection="agent2_memory")
```

**Multi-agent on shared Milvus:**
- Each agent gets its own collection
- Collections are isolated (queries don't bleed across agents)
- Can use same Milvus server or Zilliz Cloud cluster
- Each agent can have different embedding provider (at index time)

**CLI support:**
```bash
# Index agent1's memory
memsearch index ./memory/agent1/ --collection agent1_memory

# Search agent2's memory
memsearch search "debug log" --collection agent2_memory
```

**Perfect for GENIE + GENIE:**
- GENIE dispatcher writes summaries to `~/.genie/dispatch/memory/`
- Each GENIE worker gets its own collection: `worker_AURORA`, `worker_FRIDAY`, etc.
- Central Milvus server (local or Zilliz Cloud) holds all worker memories
- GENIE queries specific worker memory: `memsearch search <query> --collection worker_AURORA`

---

## 6. GitHub Activity & Maturity

### Vitals
- **Created:** 2026-02-09 (new project, ~7 weeks old)
- **Last push:** 2026-03-25 (4 days ago, very active)
- **Latest release:** v0.1.19 (2026-03-23)
- **Python:** 3.10+
- **Stars:** 1,032 (strong adoption)
- **Forks:** 94 (community engagement)

### Recent Commit Activity (past 15 commits)

| Date | Commit |
|------|--------|
| 2026-03-25 | Merge PR #223 |
| 2026-03-24 | fix: use cat fallback when timeout unavailable on macOS |
| 2026-03-23 | fix: docs rendering for Zilliz Cloud |
| 2026-03-23 | docs: promote Zilliz Cloud, add comparison table |
| 2026-03-23 | chore: bump to 0.1.19 + ccplugin 0.2.9 |
| 2026-03-23 | docs: update compact --source examples |
| 2026-03-22 | Merge PR #216 |
| 2026-03-22 | chore: bump to 0.1.18 + ccplugin 0.2.8 |
| 2026-03-22 | fix: isolate index errors per file, reduce OpenAI batch size |

**Conclusion:** Active development, bug fixes + feature refinement every few days.

---

## 7. Known Issues & Limitations

### Open Issues (as of 2026-03-29)

**Critical / Blocking:**
- None identified

**Known Bugs:**
- `ccplugin: .memsearch created in subdirectories when CLAUDE_PROJECT_DIR is unset` — config location issue
- `ccplugin: stop hook silently fails on macOS — no session summaries saved` — transcript capture timing
- `Milvus Lite does NOT work on Windows` — requires remote Milvus or Zilliz Cloud for Windows users

**Feature Gaps (tracked but not critical):**
- `feat: improve search quality with MPS acceleration, better models, and cross-encoder reranking` — future enhancement
- `feat(hooks): add SubagentStop hook to capture subagent memory` — not yet implemented
- `Google embedding provider: support Vertex AI` — pending

**Test Coverage Gaps:**
- CLI help paths, compact prompts, config edge cases, watcher debounce, etc. — mostly test infrastructure

### Limitations

1. **Windows + Milvus Lite:** Must use Docker/remote Milvus or Zilliz Cloud
2. **Search quality:** ONNX model slightly lower than text-embedding-3-small (~1%)
3. **No built-in reranking:** RRF only (no learned reranker)
4. **Single-file watch:** `memsearch watch` handles one directory; multiple watchers need separate processes
5. **API key management:** Embedding providers require env vars (no inline secrets)

---

## 8. Comparison to File-Based Memory Systems

### memsearch Advantages

| Feature | memsearch | File-Only | Winner |
|---------|-----------|-----------|--------|
| **Semantic search** | Vector DB + BM25 | Grep / regex only | memsearch |
| **Deduplication** | Content hash (auto) | Manual | memsearch |
| **Scale** | 100K+ chunks efficiently | Slow on large files | memsearch |
| **Framework integration** | LangChain, LangGraph, CrewAI ready | Manual parsing | memsearch |
| **Live sync** | File watcher + auto-index | Manual `git` | memsearch |
| **Multi-agent** | Collection isolation | Filename tricks | memsearch |
| **API key required** | Optional (ONNX free) | N/A | Tie (memsearch can be free) |
| **Git-friendly** | ✅ Markdown only | ✅ Always | Tie |
| **Complexity** | Higher (Milvus dependency) | Minimal | File-only |
| **Setup time** | 5 min | Immediate | File-only |

### memsearch Disadvantages

1. **Milvus dependency:** Adds complexity (though Lite is zero-config locally)
2. **Vector DB on Windows:** Lite doesn't work; need Docker/remote
3. **ONNX model download:** ~558 MB on first run
4. **Search quality tuning:** Requires understanding of embedding models
5. **Collection management:** Extra step for multi-agent (though well-supported)

### When to Use Each

**Use File-Based Markdown Only:**
- Simple grep-based retrieval is enough
- No semantic search needed
- Minimizing dependencies
- Minimal setup time

**Use memsearch:**
- Semantic search needed (similar meaning, not just keywords)
- 10K+ chunks (performance matters)
- Multi-agent memory isolation required
- Claude Code plugin features needed (auto-summarize, session tracking)
- Want future-proof vector search capabilities

---

## 9. Claude Code Plugin Deep Dive

### What's Unique

1. **Auto-Summary:** Every session summarizes to daily `.md` automatically
2. **No Manual Commands:** Just install and chat — memory works invisibly
3. **Progressive Disclosure:** 3-layer recall strategy:
   - Cold start: inject recent daily summaries
   - User asks: hint "[memsearch] Memory available"
   - Memory-recall skill: subagent does semantic search
4. **Transcript Parsing:** Extracts turns from JSONL, parses markdown-compatible format
5. **Background Watching:** Singleton `memsearch watch` keeps index current

### Lifecycle Hooks

| Hook | Timing | Role |
|------|--------|------|
| **SessionStart** | Session begins | Start watcher, inject recent memories, display config |
| **UserPromptSubmit** | Before Claude processes | Lightweight hint: "[memsearch] Memory available" |
| **Stop** | Async, non-blocking | Extract last turn, summarize with Haiku, append to daily `.md` |
| **SessionEnd** | Session ends | Clean up watcher process |

### Memory Recall Skill

- Spawns as **fork subagent** (independent context)
- Queries Milvus for relevant chunks
- Returns curated summary (not raw chunks)
- Used when Claude needs context

---

## 10. Factual Summary: What's Verified vs. Speculative

### Verified (From Code/Docs)
✅ ONNX uses bge-m3-int8, downloads ~558 MB
✅ Default embedding: text-embedding-3-small (OpenAI) OR bge-m3-onnx-int8 (Claude plugin)
✅ Milvus Lite does NOT work on Windows
✅ Supports 6 embedding providers (OpenAI, Google, Voyage, Ollama, Local, ONNX)
✅ Git-friendly: markdown-only source, vector DB is derived index
✅ Hybrid search: dense vector + BM25 + RRF reranking
✅ Content deduplication: SHA-256 hashing, prevents re-embedding
✅ Multi-agent support: via Milvus collections
✅ 1,032 stars, active development (commits every few days)
✅ Claude Code plugin ships with memsearch
✅ No token overhead for normal search (ONNX is free)

### Not Verified (Would Require Testing)
❓ Actual search latency on large memory bases (10K+ chunks)
❓ Real embedding quality differences between ONNX and OpenAI (benchmark exists but untested)
❓ Windows + remote Milvus latency (not tested)
❓ Memory overhead for `memsearch watch` process (likely minimal)

### Known Limitations
⚠️ Windows cannot use Milvus Lite (stated in code)
⚠️ macOS stop hook has timing issues (issue #18 open)
⚠️ ONNX model downloads on first run (can hang if slow connection)

---

## 11. References & URLs

### Official Resources
- **GitHub:** https://github.com/zilliztech/memsearch
- **Documentation:** https://zilliztech.github.io/memsearch/
- **Claude Code Plugin Docs:** https://zilliztech.github.io/memsearch/claude-plugin/
- **CLI Reference:** https://zilliztech.github.io/memsearch/cli/
- **Integration Docs:** https://zilliztech.github.io/memsearch/integrations/
- **PyPI:** https://pypi.org/project/memsearch/

### Key Files in Repo
- `README.md` — overview, quick start, installation
- `src/memsearch/core.py` — main API (MemSearch class)
- `src/memsearch/store.py` — Milvus storage layer
- `src/memsearch/embeddings/` — 6 embedding providers
- `ccplugin/README.md` — Claude Code plugin architecture
- `pyproject.toml` — dependencies, extras, versions

### Upstream Dependencies
- **Milvus:** https://milvus.io/ (vector database)
- **Zilliz Cloud:** https://cloud.zilliz.com/ (managed Milvus)
- **OpenClaw:** https://github.com/openclaw/openclaw (memory architecture inspiration)

---

## Recommendation Summary

**For GENIE/GENIE System:**
memsearch is **highly suitable** as a worker memory backend:

1. **Multi-agent collection support** — each GENIE worker (AURORA, FRIDAY, etc.) gets isolated memory
2. **ONNX default** — zero-config, no API keys needed
3. **Git-friendly markdown** — compatible with existing `.claude/` workflow
4. **Small/new project** — actively maintained, responsive to issues
5. **Claude Code plugin** — perfect for session-based workers
6. **Milvus flexibility** — local (non-Windows), Docker, or Zilliz Cloud

**Caveats:**
- Windows users would need Zilliz Cloud or Docker
- Adds Milvus dependency (manageable)
- ONNX download on first run (~558 MB, ~2 min on normal connection)

**Integration Plan:**
- Each worker: `MemSearch(paths=[f"~/.claude/dispatch/{worker_name}/memory"], collection=f"worker_{worker_name}")`
- Central Milvus server: `http://localhost:19530` or Zilliz Cloud
- GENIE queries via CLI: `memsearch search <query> --collection worker_AURORA`
- Workers auto-summarize sessions to daily markdown
