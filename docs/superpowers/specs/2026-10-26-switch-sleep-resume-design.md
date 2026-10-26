# Switch sleep and stream resume

Build a test client from [Moonlight-Switch v1.5.0](https://github.com/XITRIX/Moonlight-Switch/tree/v1.5.0), matching the user's working release. HOME/sleep must disconnect streaming without terminating the host application. Reconnecting must request the configured resolution and optimization policy, including 1080p, so Sunshine can restore the stream display mode.

## Approaches

The user chose a dedicated GitHub fork with a local checkout, over a local-only experiment or vendoring into homelab. Adapt the complete [PR #318](https://github.com/XITRIX/Moonlight-Switch/pull/318) with attribution, including deferred teardown and single subscription lifetime. Restrict the suspend behavior to Switch. Keep fresh-launch behavior and explicit quit behavior unchanged.

## Scope and validation

Two separate fix commits. Preserve the installed client and configuration. Do not open upstream PRs or change Sunshine. Host desktop restoration while disconnected remains unchanged. First validate protocol and focus-loss logic on the host and compile a Switch NRO. Then perform device tests with paused Stardew/Steam Big Picture and a separate AAA game: repeated HOME and sleep cycles, reconnect at 1080p, game still running, overlay reopening, and rapid sleep during connection. Automated tests cannot prove console sleep stability.

The user approved this scope in the conversation and asked to continue. Build locally if a toolchain is available; otherwise use a pinned devkitPro container in this fork's GitHub Actions. Hardware installation requires access to the Switch, with a backup before replacement. No release is labelled stable before hardware testing.
