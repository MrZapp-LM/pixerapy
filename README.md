# PixeraPy

Python client for the [AV Stumpfl PIXERA](https://pixera.one) JSON API.

`NOT AN OFFICIAL PIXERA PROJECT`

- Covers **API revision 481 (PIXERA 26.1 R39)**: 881 functions and class methods, generated from the official API description, with Pixera's own comments as docstrings.
- Drop-in compatible with PixeraPy 0.381 / 0.461 by Ted Charles Brown: same `Pixera` and `API` classes, same call style.
- No dependencies. Works with JSON/TCP, JSON/TCP (dl) and HTTP access points.
- Persistent connections and monitoring events.

This is a continuation of [PixeraPy by Ted Charles Brown](https://github.com/Tedcharlesbrown/Pixera-TCB/tree/main/01-Custom/03-API). The published `PixeraPy 0.461.1` on PyPI still contains the revision 381 functions (PIXERA 2.0.40); this fork brings it to the current API.

## Install

```
pip install git+https://github.com/MrZapp-LM/pixerapy
```

The import name is still `PixeraPy`, so uninstall the old package first (`pip uninstall PixeraPy`) to avoid the two shadowing each other.

## Pixera setup

In Pixera open **Settings > API** and add an access point, e.g. **JSON/TCP** on port **1400**. Allow the port in the firewall of the Pixera machine if you connect from another computer.

## Quick start

```python
from PixeraPy import API, Pixera

pixera = Pixera("127.0.0.1", 1400)

print(pixera.send(API.Utility.getApiRevision()))          # 481

for screen in pixera.send(API.Screens.getScreens()):       # list of handles
    print(pixera.send(API.Screens.Screen.getName(screen)))

timeline = pixera.send(API.Timelines.getTimelineFromName("Timeline 1"))
pixera.send(API.Timelines.Timeline.play(timeline))
pixera.send(API.Timelines.Timeline.applyCueWithNumberString(timeline, "2.1"))
```

Every API function only *builds* a request (`[method, param_names, values]`); `pixera.send(...)` sends it and returns the `result` of the reply. Class methods (Screen, Timeline, Layer, Cue, ...) take the object handle as first argument.

Old style calls keep working: `API.getScreens()`, `API.Screen.getName(handle)`, `api = API(); api.getScreens()`.

## Documentation

- [Getting started](docs/getting-started.md): connection, protocols, handles, optional parameters, errors
- [Monitoring](docs/monitoring.md): persistent connections, polling and event mode
- [API reference](docs/api-reference.md): every function of revision 481 (generated)
- [Updating to a new Pixera version](docs/updating-the-api.md): regenerate from a new API description
- [Changelog](CHANGELOG.md)

## Development

```
pip install -e . pytest
pytest
```

The tests run against a small fake Pixera server, no Pixera installation needed.

## License

MIT. Original work © 2023 Ted Charles Brown, continued © 2026 MrZapp-LM.
