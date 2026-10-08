# Changelog

Release entries will describe user-visible changes and limitations. No release has been made.

## Unreleased

### Added

- An explicit source-publication inventory (54 files initially, 55 after MIT adoption), external dependency notices, and a private-reporting setup proposal. Candidate-only local reproduction passed existing tests and examples; no publication or repository setting change was performed.
- A root MIT LICENSE with Copyright (c) 2026 Masaki Takemura, adopted following the maintainer’s instruction. Both READMEs and the source candidate reflect the adopted license.
- A pinned 320-line synthetic infrastructure log, independently authored evidence expectations, and a reproducible six-case rg/search/masking comparison. Records missed late evidence, an unclassified secret, overbroad masks, a nonsecret counter false positive, duplicate observations, and private-key middle excerpts without using real logs.
- Explicit `search --mask-rules` TOML policies with builtin Bearer, credential assignment, and known private-key masking plus custom Python regex. Matched files are checked in full before excerpting; masks preserve Unicode character positions and line endings.
- Masking resource limits, isolated deadline-bounded regex workers, withheld query/glob metadata, source consistency checks, and synthetic masking boundary tests. Policy application does not imply complete secret detection or sharing approval.
- A local development `search` CLI using existing rg: case-sensitive literal search, source positions, bounded text/JSON responses, total counts, explicit omissions, deadlines, and failure handling without raw backend diagnostics. No persistent cache.
- Synthetic search integration and subprocess-boundary tests, a CLI contract, and a Linux CI test definition; no remote CI result or real-workflow benefit claim.
- Japanese and English READMEs describing the planned log editing and review workflow.
- Design, threat model, milestones, local evaluation template, and OSS release readiness checklist.
- Contribution and security policies, community guidance, Issue and PR templates.
- Synthetic examples and documentation checks with a proposed GitHub Actions workflow.
- Concept and business review, conditional execution tasks, a review workflow sketch, and an infrastructure evidence-report template.
- A workflow linking conclusions to supporting and conflicting evidence, a fully synthetic report example, and five bounded report-workflow tasks.
- Work-scope and review-result fields in the infrastructure report template for IR-01 and IR-03.
- Report masking definitions covering complete credential masking, consistent aliases, attachment review, evidence traceability, and conditions for holding a submission draft.
- A bounded synthetic trial with corrected conclusions, evidence references, masking, and a separate submission sample; no real-workflow value claim.
- A mixed-document requirements and provisional-design evaluation plan, extraction and source-reference contracts, a traceability template, and bounded log aggregation conditions.

### Changed

- Set the completion target to a small portfolio CLI with PF-0 through PF-3 milestones: working implementation, reproducible design evidence, an OSS publication candidate, and explicitly approved source publication. Close feature development at PF-1; keep business/workflow research and parser/cache ideas as references rather than prerequisites.
- Rewrite both READMEs around the implemented search and TOML masking, with a synthetic re-search demonstration, code-search usage, known failure cases, and separate local-completion/publication states.
- Put redaction CLI development and comparison trials on hold after confirming that linking conclusions to evidence and preparing reports is the main difficulty.
- Previously prioritized DR-01 through DR-05 for the document-to-design hypothesis; now retain DR, LG, IR, and the initial review CLI plan as references outside the portfolio completion path.
- Prioritize one existing report format and a bounded evaluation before considering any limited automation.
- Make session-only repeated-value editing, sharing-range selection, individual false-positive review, and final-text consistency part of the conditional design.
- Connect the validation plan to infrastructure analysis reports, while keeping analysis and evidence organization outside the redaction CLI's scope.

### Pending

- Report-workflow and document-to-design trials remain on hold and are not required for portfolio completion.
- Redaction detector selection and the `review` CLI remain on hold.
- License adoption, copyright holder confirmation, and private vulnerability reporting setup.
- Maintainer approval for publication and distribution.
