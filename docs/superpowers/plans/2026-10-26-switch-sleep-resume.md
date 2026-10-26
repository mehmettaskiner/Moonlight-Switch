# Switch sleep and resume implementation plan

> Execute inline using the executing-plans and test-driven-development skills.

**Goal:** Disconnect safely on Switch focus loss and request the selected display mode on resume.
**Architecture:** Adapt PR #318 into StreamingView; preserve the launch protocol and add missing resume parameters in gs_start_app. Keep platform guards and existing host quit semantics.
**Tech Stack:** C++17, Borealis, libgamestream, devkitPro, Python unittest host harness.
**Spec:** ../specs/2026-10-26-switch-sleep-resume-design.md

## Global constraints

Start at v1.5.0. Separate conventional fix commits; attribute PR authors. No upstream PR or Sunshine changes. Existing NRO/settings retained for rollback. Hardware validation remains explicit.

## Review focus

- Focus loss during connection and repeated overlays: no leaked callbacks or use after free.
- Wake before next draw: pending disconnect persists and avoids renderer access.
- Stream-only disconnect never sends host cancellation.
- Resume with optimization disabled and FPS above 60: match launch policy.
- HTTP error and missing XML: preserve existing handling.

## Task 1: Switch focus loss

Files: app/include/streaming_view.hpp, app/src/streaming_view.cpp, tests/test_stream_lifecycle.py.
- [x] Add host harness executing actual focus callback and pre-render draw logic with recording input/session fakes; first assert missing behavior fails.
- [x] Adapt final PR #318: subscribe once in constructor, unsubscribe in destructor, disable/drop input on loss, defer terminate(false) to draw before renderer. Guard Switch-only additions.
- [x] Test gained focus, loss, repeated loss, regained focus before draw, already terminated, and stream-only shutdown. Commit with attribution.

## Task 2: Resume display mode

Files: app/src/libgamestream/client.cpp, tests/test_stream_lifecycle.py.
- [x] Compile actual gs_start_app in a host harness with a recording HTTP boundary; assert resume mode and sops, watch failure.
- [x] Share FPS calculation with launch; add mode and sops to resume URL without changing existing key/query data.
- [x] Test launch/resume, 1080p/720p/1440p, sops on/off and FPS cap, HTTP errors and unsupported 4K. Commit.

## Task 3: Build and review

Files: .github/workflows/switch-test-build.yml, docs/switch-sleep-resume-testing.md.
- [ ] Use pinned build image; fork-only branch workflow builds NRO/ELF and runs host tests; artifact includes checksum and source identity. Preserve existing upstream workflow.
- [ ] Review complete diff, run all host tests, build Switch artifact, download and validate checksum/header.
- [ ] Document rollback and pending device acceptance. Push only to the user's fork. No upstream PR.

## Review follow-up

Independent review found that PR #318's deferred stop could still destroy a session with startup callbacks pending. Before hardware testing, guard pending host connection and session start, deliver startup completion on the main thread, and suppress autoreconnect after disconnect request. This is necessary for HOME during loading, not an unrelated feature. The added host tests exercise deferred teardown and completion delivery; real delayed-network device testing remains pending.
