# Getting started

## 1. Pixera access point

Pixera only answers on ports that are configured as API access points:
**Settings > API**, add a port and pick the mode.

| Pixera mode       | `protocol=` | Notes |
|-------------------|-------------|-------|
| JSON/TCP          | `"TCP"` (default) | Messages framed with a `pxr1` + size header. Recommended. |
| JSON/TCP (dl)     | `"TCP_DL"`  | Messages end with the delimiter `0xPX`. |
| HTTP/TCP          | `"HTTP"`    | JSON-RPC via HTTP POST. One request per HTTP call, no monitoring. |

Several clients can use the same port at the same time.

## 2. Connect

```python
from PixeraPy import API, Pixera

pixera = Pixera("192.168.1.10", 1400)              # JSON/TCP
pixera_dl = Pixera("192.168.1.10", 1401, protocol="TCP_DL")
pixera_web = Pixera("192.168.1.10", 8080, protocol="HTTP")
```

`Pixera(ip, port, protocol="TCP", timeout=10.0, keep_alive=False)`

By default each `send()` opens a connection, sends one request, waits for the reply and closes
the connection. That is simple and robust. For many calls in a row, or for monitoring, keep one
connection open:

```python
with Pixera("192.168.1.10", 1400) as pixera:       # keep_alive inside the block
    for i in range(100):
        pixera.send(API.Compound.setOpacityOnTimeline("Timeline 1", i / 100))
```

or `Pixera(..., keep_alive=True)` and `pixera.close()` at the end.

`send(..., protocol=..., port=...)` overrides protocol and port for a single call.

## 3. Calls

Every function in `API` builds a request; `send()` executes it:

```python
request = API.Screens.getScreenNames()    # ['Pixera.Screens.getScreenNames', [], []]
names = pixera.send(request)               # ['Screen 1', 'Screen 2']
```

The structure of `API` follows the Pixera API:

```
API.Utility.getApiRevision()
API.Timelines.getTimelines()
API.Timelines.Timeline.play(timeline_handle)
API.Timelines.Layer.setOpacity(layer_handle, 0.5)
API.Settings.SettingsGeneral.getFadeToTimeDuration()
API.Direct.Screen.setPosition(screen_handle, 1.0, 2.0, 0.0)
```

For compatibility with older PixeraPy versions all namespace functions and classes are also
available directly: `API.getTimelines()`, `API.Timeline.play(h)`. Where the same class name exists
twice (`Direct.Screen` and `Screens.Screen`, also Projector, Param, Perspective) the short form
points to the normal one, use `API.Direct.*` for the Direct variants.

`API.API_REVISION` / `PixeraPy.API_REVISION` is the revision the functions were generated from.
Compare it with `pixera.send(API.Utility.getApiRevision())` to see whether Pixera is newer.
`API.Utility.getHasFunction("Pixera.Timelines.Timeline.startPreviewEdit")` checks single functions.

### Handles

Pixera objects (screens, timelines, layers, cues, clips, resources, ...) are addressed by handles,
large integers. Functions that return objects return handles, class methods take the handle as
first argument:

```python
timeline = pixera.send(API.Timelines.getTimelineFromName("Show"))
for layer in pixera.send(API.Timelines.Timeline.getLayers(timeline)):
    print(pixera.send(API.Timelines.Layer.getName(layer)))
```

Handles stay valid while the object exists in the project.

### Optional parameters

Parameters marked `optional<...>` in the Pixera API default to `None` and are then left out of the
request, so Pixera uses its own default:

```python
pixera.send(API.Timelines.Layer.setOpacity(layer, 0.0, fadeTimeMs=3000))   # 3 s fade
pixera.send(API.Timelines.Layer.setOpacity(layer, 1.0))                     # immediately
pixera.send(API.Screens.Screen.setPosition(screen, zPos=2.5))               # only z
```

### Return values

`send()` returns the `result` of the JSON-RPC reply: numbers, strings, lists, dicts (for structs
such as `ScreenPosValues` -> `{"x": .., "y": .., "z": ..}`), or `None` for functions without result.
Each function's docstring ends with the Pixera signature and the type Pixera returns.

`send(..., raw_output=True)` returns the full reply dict, `verbose=True` prints request and reply.

### Errors

If Pixera answers with a JSON-RPC error, `send()` raises `PixeraError` (`.code`, `.message`,
`.request`). Network problems raise the usual `OSError` / `ConnectionError` / `socket.timeout`.

```python
from PixeraPy import PixeraError

try:
    pixera.send(API.Timelines.getTimelineFromName("Missing"))
except PixeraError as error:
    print(error.code, error.message)
```

### Control modules and manual calls

Anything Pixera understands can be sent as a list `[method, param_names, values]`:

```python
pixera.send(["NewModule.Test"])                                         # Pixera Control module
pixera.send(["Pixera.Utility.outputDebug", ["message"], ["Hello"]])
```

### DIRECT protocol

`protocol="DIRECT"` is kept from PixeraPy 0.381: it inserts `.Direct` after `Pixera.` in the
method name and sends via JSON/TCP. Prefer the explicit `API.Direct.*` functions; they match the
real method names of the Direct API (`Pixera.Direct.Screen.setPosition`, ...).
