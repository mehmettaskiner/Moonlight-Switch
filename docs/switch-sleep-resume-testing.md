# Moonlight Switch sleep/resume test build

Based on [XITRIX v1.5.0](https://github.com/XITRIX/Moonlight-Switch/tree/v1.5.0). This is a test build, not a verified sleep-crash fix.

Changes:
- Switch window focus loss disables input and defers stream-only teardown until the next draw, before renderer access. Adapted from [quadseven's PR #318](https://github.com/XITRIX/Moonlight-Switch/pull/318), including its deferred teardown and single-subscription fixes.
- Resume requests carry the configured display mode and optimization policy, matching fresh launch. Sunshine remains responsible for display configuration.

## Install and rollback

Before replacement, copy the currently installed NRO and its configuration directory off the SD card. A different NRO filename does not isolate settings. Verify SHA256SUMS and SOURCE_COMMIT.txt. Close Moonlight before replacing it via FTP. Run in full application mode. Keep the original NRO available for rollback; restoring it restores client code, not host display configuration.

No automatic installation, system module, or Sunshine setting change is part of this build. The fork workflow has read-only repository permissions and uploads temporary Actions artifacts; it creates no release or PR.

## Device acceptance (pending)

1. Enable the client's Optimize game settings option when testing Sunshine display-mode changes; the patch preserves that preference rather than forcing it on. Fresh launch Steam Big Picture at the configured 1920x1080 resolution. Confirm audio, controller input, and video.
2. Start Stardew, pause it, press HOME, return to Moonlight. Expect stream disconnect; the PC game remains running. Reconnect to the existing host session and confirm 1080p plus the same game state.
3. Repeat using Power/sleep, then wake and reconnect. Repeat three times and include one longer sleep. No orange screen or Atmosphere crash is acceptable.
4. Open/close Moonlight's overlay repeatedly, then repeat HOME and sleep. Reconnect multiple times to exercise subscription lifetime.
5. Separately test a fullscreen/borderless AAA game. Check aspect ratio, UI, and fullscreen state after reconnect.
6. Check explicit Disconnect and Quit remain distinct. Only an intentional Quit may terminate the host app.
7. Test sleep/HOME during connection/loading separately. This build waits for pending host connection and session startup to settle before teardown, and suppresses automatic reconnect once disconnect is requested. Slow or unreachable hosts may delay dismissal until startup times out.

Record the source commit, game, each action, requested and actual host resolution, and outcome. The host can still return to ultrawide while disconnected. If that disrupts game layout, handle Sunshine display persistence separately. The client does not pause games automatically.

## Automated coverage and limits

Run `python3 -m unittest discover -s tests -v`. Host harnesses compile actual production function bodies against recording transport/input boundaries, under ASan/UBSan. Five tests cover queued teardown before rendering, waiting for initial connection/startup, main-thread startup completion, serialized reconnect handling (including termination during startup), queued-event invalidation after session replacement, and request parameters across launch/resume, resolutions, optimization policies and FPS. They do not simulate the Switch OS, GPU, actual callback subscription lifetime, or network/service behavior during sleep. The Switch build checks SDK integration; hardware acceptance is still necessary.

## Known upstream limits

This remains a hardware-unverified test build. The generation check discards termination work queued before a session is destroyed or replaced. The upstream global callback API does not identify the originating session; an old detached callback that first executes after replacement cannot be identified by that check. This is a pre-existing limitation. Manual quitting during startup and unrelated decoder/GPU behavior are not established fixed by these tests.
