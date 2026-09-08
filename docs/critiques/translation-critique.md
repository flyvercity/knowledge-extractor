# Specification Critique: Translation to English (`docs/specs/translation.md`)

**Pass Number:** 1  
**Spec Document:** `docs/specs/translation.md`  
**Date:** September 8, 2026  

---

## Executive Summary

The specification `docs/specs/translation.md` outlines an opt-in translation capability using a dedicated final pass (`--translate-from`) powered by an AI text model (defaulting to `google/gemini-2.5-flash`). Overall, the feature is well-conceived: running translation as step 5b on fully assembled Markdown after AI cleanup minimizes token usage and keeps core extraction stages decoupled.

However, the critique identified key technical and usability risks that should be resolved before implementation:
1. **Unhandled Exception in Chunking (Must-Address)**: Task 2 specifies catching only `AIBadRequestError` during chunked translation. Unhandled `AIProviderError` exceptions (network issues, rate limits, 500 status) will crash the pipeline instead of degrading gracefully or retaining original text.
2. **Incremental Skip UX Footgun (Recommendation)**: Re-running the tool with `--translate-from` on an existing output directory will skip all files because the output Markdown files already exist.
3. **Low Chunking Threshold (Recommendation)**: A 10,000-character (~2,500 token) chunk threshold is unnecessarily small for modern LLMs (e.g. Gemini 2.5 Flash), adding API latency and context fragmentation.
4. **Mermaid Syntax Corruption Risk (Recommendation)**: Translating labels inside Mermaid code blocks via general prompt instructions frequently breaks diagram syntax if node IDs or structural keywords are modified.

---

## Product Lens Findings

### 1a. Problem Validation & Scope
- **P3 (Question)**: Free-form `--translate-from` parameter lacks validation.
  - *Finding*: Passing free-form strings directly into LLM prompts without sanitization or validation creates a potential prompt injection vector (e.g. `--translate-from "German. Ignore previous instructions..."`).
  - *Suggestion*: Sanitize `translate_from` input in CLI parsing to disallow line breaks or unusual control characters before formatting into prompts.

### 1b. User Value Assessment & Edge Cases
- **P2 (Recommendation)**: High risk of Mermaid syntax corruption during translation.
  - *Finding*: Requesting translation of diagram node labels in prose prompts without explicit structural guidelines often leads to LLMs altering node identifiers (e.g., `A[Text]` converted to `[Translated Text]`) or Mermaid keywords (`graph`, `subgraph`, `end`), breaking diagram rendering.
  - *Suggestion*: Add explicit negative rules and examples in `TRANSLATE_PROMPT` demonstrating that node identifiers and structural syntax MUST remain untouched while only node display strings inside brackets/quotes are translated.

### 1d. Edge Cases & User Experience
- **P1 (Recommendation)**: Incremental skip behavior hides translation from existing outputs.
  - *Finding*: If a user previously extracted documents without `--translate-from`, running `knowledge-extractor --input ... --output ... --translate-from German` will skip processing for all existing output files without warning.
  - *Suggestion*: Update the spec (and README) to explicitly document this interaction, and log a warning in `cli.py` if `--translate-from` is set while skipping files due to pre-existing outputs.

---

## Engineering Lens Findings

### 2a. Architecture Soundness
- **E2 (Recommendation)**: Global singleton fragmentation in `pipeline.py`.
  - *Finding*: Spec proposes adding `_get_translate_ai` and `get_translate_ai_client()` alongside `_get_ai` and `get_ai_client()`. Managing separate module-level singletons duplicates boilerplate and complicates end-of-run usage aggregation.
  - *Suggestion*: Consider generalizing `_get_ai(model)` to cache instances in a dictionary by model name (e.g. `_ai_clients[model]`), or aggregate total usage across all `AIClient` instances in `ai_client.py`.

### 2b. Failure Mode Analysis
- **E1 (Must-Address)**: Unhandled `AIProviderError` during chunked translation.
  - *Finding*: Task 2 specifies catching `AIBadRequestError` per chunk and logging a warning. However, transient errors, rate limits (429), or server errors (500) raise `AIProviderError` from `_call`. If `AIProviderError` occurs during a chunk, it bypasses the try/except block, crashing the pipeline for the entire document.
  - *Suggestion*: Catch `(AIBadRequestError, AIProviderError)` per chunk in `translate_content` (or log a warning and retain the original chunk text) so the pipeline degrades gracefully instead of failing unhandled.

### 2d. Performance & Scalability
- **E3 (Recommendation)**: Overly aggressive chunking threshold (10,000 chars).
  - *Finding*: 10,000 characters is ~2,500 tokens. Modern target models (such as `google/gemini-2.5-flash`) support context windows exceeding 1M tokens. Small chunk sizes increase API roundtrips, multiply cost, and risk splitting context across section headers.
  - *Suggestion*: Increase the default `chunk_size` for translation to `50000` or `100000` characters, keeping single-pass execution for almost all standard technical documents.

### 2g. Dependencies & Integration Risks
- **E4 (Recommendation)**: Arbitrary line-based splitting can break Markdown blocks.
  - *Finding*: In `_split_into_chunks`, falling back to paragraph/line splitting when a section exceeds `chunk_size` can split code blocks, tables, or LaTeX display math (`$$...$$`) across chunk boundaries, leading to syntax corruption.
  - *Suggestion*: Document this risk and ensure `_split_into_chunks` checks for code block fences (` ``` `) when splitting oversized sections.

---

## Cross-Lens Synthesis

- **X1 (Scope x Risk x Quality)**: Context Preservation & Chunking Strategy.
  Increasing `chunk_size` to 50,000+ characters (E3) directly resolves both performance bottlenecks (Engineering) and context loss across sections (Product), while reducing the chance of splitting tables or Mermaid diagrams across chunks.
- **X2 (User Experience x Operational Resilience)**: Exception Handling & Failure Transparency.
  Catching all AI provider exceptions during chunked translation (E1) guarantees that translation failures result in partial/untranslated Markdown rather than command crashes (Product UX & Engineering Reliability).

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| E1 | Engineering | 🎯 | Failure Mode Analysis | Task 2 catches only `AIBadRequestError`; `AIProviderError` will crash the pipeline during chunked translation | Catch `(AIBadRequestError, AIProviderError)` per chunk, keep original text, and log warning |
| P1 | Product | 💡 | Edge Cases & UX | Output file existence check skips translation when re-running on existing outputs | Clarify skip behavior in spec/README and log a warning in `cli.py` when skipping with `--translate-from` |
| P2 | Product | 💡 | User Value / Edge Cases | Prompting LLM to translate Mermaid labels risks corrupting graph syntax and node IDs | Strengthen `TRANSLATE_PROMPT` with explicit negative rules and Mermaid syntax preservation examples |
| E2 | Engineering | 💡 | Architecture Soundness | Separate `_get_translate_ai` singleton duplicates state management and usage tracking | Cache `AIClient` instances by model key or aggregate usage metrics across all active clients |
| E3 | Engineering | 💡 | Performance & Scalability | 10,000 character chunk threshold (~2.5k tokens) causes unnecessary context fragmentation and API overhead | Increase default translation `chunk_size` threshold to 50,000 characters |
| E4 | Engineering | 💡 | Integration Risks | Line-based fallback in `_split_into_chunks` can split Markdown code blocks or tables | Avoid splitting inside fenced code blocks or increase chunk threshold to prevent fallback |
| P3 | Product | 🤔 | Security / Validation | Free-form `--translate-from` CLI string is passed directly into LLM prompt template | Validate/sanitize `translate_from` string against newline/control characters |

---

## Verdict

⚠️ **PROCEED WITH UPDATES**

The overall architecture for translation is sound and aligns well with the existing pipeline. Resolving the must-address exception handling issue (E1) and addressing the key recommendations (P1, P2, E3) will make the implementation resilient and robust.

---

## Proposed Remediation & Spec Edits

### Edit 1: Fix Exception Handling & Increase Chunk Threshold in Task 2 (Addressing E1, E3, P2)

Update `docs/specs/translation.md` in **Task 2**:
- Change chunk size default from `10000` to `50000`.
- Update prompt instructions for Mermaid preservation with explicit rules.
- Change exception handling requirement from `catch AIBadRequestError` to `catch (AIBadRequestError, AIProviderError)`.

### Edit 2: Document Incremental Skip & CLI Warning in Task 3 & 4 (Addressing P1)

Update `docs/specs/translation.md` in **Requirements** and **Task 4**:
- Clarify that if outputs exist, user must use `clear` or delete output files to trigger translation.
- Log an informational warning if `--translate-from` is passed but a file is skipped due to existing output.

---

Would you like me to apply these changes to `docs/specs/translation.md`? (all / select / none)
