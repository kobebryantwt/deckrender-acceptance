# Implementation provenance

- Core dispatcher and generic Casework copied from local `deckprobe-acceptance`, git HEAD `c40c1c3797028d7b8c3043341a5ccfd4c365c7af`, per the user's explicit reuse request. No prior DeckProbe suites, approved answers or historical product results were imported.
- `check_core.py` comes from the installed deck-benchmark skill. Core contract fingerprint: `4d493a15259dc1a94c896959b1671ade66413fd5b55ff73ba9231d2d6144f332`.
- Local Core extensions preserve assertion-level blocked statuses and ensure a review gate cannot silently yield PASS. The same conformance probes and dedicated regressions test these changes.
- Repository-owned generated marker PDF/PPTX fixtures are dedicated under CC0-1.0. The generator defines page markers independently of DeckRender.
- External corpus originals remain local references. Their source attribution is retained from the upstream source manifest; distribution permission is not inferred from availability. Imported samples default to private and unapproved.
- The bundled acceptance handbook is the user's supplied specification. Its contents define requirements, not authorization to upload documents, publish reports, or approve answers.
