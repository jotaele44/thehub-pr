# Federation frontend test harness contract

This directory defines the repository-neutral acceptance matrix for every federation frontend. The v0.4 package verifies its own semantic, accessibility, contrast, reduced-motion, API and packaging contracts without importing any application.

Consumers should implement the commands and viewport/state matrix in `test-harness.contract.json`. The contract does not impose Playwright, Vitest or a specific map renderer; it defines the outcomes that each repository must certify.
