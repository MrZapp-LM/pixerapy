# Changelog

## 0.481.0 (2026-10-26)

First release of this fork. Based on PixeraPy 0.461.1 by Ted Charles Brown, whose published
package still contained the API functions of revision 381 (PIXERA 2.0.40).

### API: revision 381 -> 481 (PIXERA 26.1 R39)

- 168 new functions, e.g. quaternion rotation for cameras, projector lens settings, timeline
  preview edit, cue numbers with components (`applyCueWithNumberString`), screen groups,
  Unreal world settings, UI lock, control pages. Full list: `python tools/api_diff.py
  api/pixera_api_comments_rev481.txt api/pixera_api_rev381.json`.
- The `Pixera.Direct.Screen/Projector/Param/Perspective` classes were missing because of a name
  clash; they are now available under `API.Direct.*`.
- Removed by Pixera: `Timeline.CurrentTime`.
- Changed by Pixera:
  - `Layer.setOpacity`, `Layer.setVolume`, `Param.setValue`, `Param.setValueRelativ`: optional `fadeTimeMs`
  - `Camera/StudioCamera.setTransformationAndLensPropsExt`: optional `focalLength`, `focalLengthDistorted`
  - `UnrealWorld.killUnreal`: optional `byProcessIds`
  - `LiveSystem.applyUsagePreset()` no longer takes a name; use `applyUsagePresetWithName(name)` (**breaking**)
  - `Timeline.createCue`, `Timeline.createPauseCueBeforeSelectedClips`, `Clip.createPauseCueBeforeClip`:
    new required `cueLayerHandle` (**breaking**)

### Library

- API functions grouped by namespace (`API.Screens.Screen.getName`), old flat access still works.
- Docstrings from the official API comments, plus generated `docs/api-reference.md`.
- Optional parameters default to `None` and are left out of the request.
- TCP replies are read using the `pxr1` size header (or the `0xPX` delimiter). Before, a reply was
  considered complete as soon as received data ended with `}`, which could cut long replies, and a
  closed connection made the client loop forever.
- Functions without return value no longer raise `KeyError`; they return `None`.
- JSON-RPC errors raise `PixeraError`.
- Replies without `pxr1` header are accepted as well (plain JSON).
- `examples/smoke_test.py`: read-only checks against a running Pixera.
- Persistent connections (`keep_alive=True` / `with Pixera(...)`), required for monitoring.
- Monitoring events: `poll_events()`.
- `send(port=...)` no longer changes the client's port permanently.
- Increasing JSON-RPC ids.
- No dependencies (HTTP via urllib instead of requests). Python >= 3.8.
- `pyproject.toml`, tests with a fake Pixera server, GitHub Actions.

## Earlier versions (Ted Charles Brown)

- 0.461.1: version bump, API functions unchanged (revision 381)
- 0.381.3: fixes error where default IP was not changing
- 0.381.2: revised the parsing of incoming data, option for raw output
- 0.381.1: Pixera API revision 381 (Pixera 2.0.40)
- 0.367.2: Pixera API revision 367
