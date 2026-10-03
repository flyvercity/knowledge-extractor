# Deferred Items — reindex-command

**Date**: 2026-10-03
**Source spec**: docs/specs/reindex-command.md
**Mode**: autoflow

## Summary

The `reindex` command shipped complete: it rebuilds a unified root `index.md` +
`manifest.json` across all subfolders of an output directory, groups by full relative
parent path, performs content-verified cleanup of nested generated artifacts (preserving
user content), excludes hidden directories, and reports document/group counts. All
critique Must-Address and Recommendation findings were applied; the code review returned
APPROVE with only LOW nits. A handful of low-priority items were intentionally deferred.

## Deferred Items

| ID | Origin | Priority | Item | Rationale / Next Step |
|----|--------|----------|------|-----------------------|
| D1 | Code Review LOW-5 | Low | `_is_hidden` only inspects parent path components, so a top-level hidden *file* (e.g. `.secret.md`) directly under the output root is still indexed. | Intentional: the helper targets hidden *directories* (`.git`, `.obsidian`). Top-level dotted `.md` files are rare and arguably should be indexed. Revisit only if a user reports noise; the fix is a one-line change to scan `rel.parts` instead of `rel.parts[:-1]`. |
| D2 | Critique P4 (🤔) | Low | A real subfolder literally named `Root` merges with root-level files under the same `## Root` index section. | Documented as an accepted low-impact cosmetic edge case in the spec. Links still resolve to the correct files. Revisit if a user hits it; a fix would reserve/escape the `Root` label. |
| D3 | Critique E5 (🤔) | Low | Cleanup resilience (locked/read-only files) is covered by a monkeypatched `OSError` test, but there is no real cross-platform locked-file integration test. | Acceptable: unit-level resilience is proven and the `OSError` path is simple. A real locked-file test is OS-specific and brittle; skip unless cleanup reliability becomes a concern. |
| D4 | Process note | Low | The branch `better-cli` is not pushed and no PR exists, so the Code Review GitHub publish and the Finalize product-manager PR comment were skipped. | When the branch is pushed and a PR opened, optionally re-post the QA/technical review (from `docs/codereviews/pr-local-reindex-review.md`) and product guidance as PR comments. |

## Suggested Follow-up

None of the deferred items are blockers. If a future iteration touches `reindex`, the most
reasonable pickups are D1 (optionally exclude top-level hidden `.md` files) and D2 (handle
a literal `Root` subfolder) — both tiny, both only worth doing if a user actually hits
them. D4 is purely a publish step gated on pushing the branch and opening a PR.
