# ADR-002 — Manifest first, download later

**Accepted.**

Every source returns `MediaManifest` before acquisition. The operator selects a pack/items before large downloads begin.

Why: media may be multi-gigabyte, long-form can still be valuable, and simplistic quality filters would throw away useful content. Metadata informs; it does not auto-reject subjective media.
