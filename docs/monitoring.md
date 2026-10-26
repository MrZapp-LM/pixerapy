# Monitoring

Pixera can report state changes (cues applied, timeline transport and position, clips added, ...).
The monitoring state is kept **per connection**, so always use a persistent connection.

## Polling

```python
import time

from PixeraPy import API, Pixera

with Pixera("192.168.1.10", 1400) as pixera:
    pixera.send(API.Utility.unsubscribeMonitoringSubject("timelinePositions"))  # optional
    while True:
        for subject in pixera.send(API.Utility.pollMonitoring()) or []:
            print(subject["name"], subject["entries"])
        time.sleep(0.1)
```

Everything that happened since the last `pollMonitoring` call is returned once; nothing is lost if
you poll slowly. For continuous values (timeline positions) only the latest value is kept.

## Event mode

Pixera can also push events as they happen:

```python
with Pixera("192.168.1.10", 1400) as pixera:
    pixera.send(API.Utility.setMonitoringEventMode("all"))       # or "onlyDiscrete", "none"
    while True:
        for event in pixera.poll_events(timeout=1.0):
            # {"id": -1, "type": "monEvent", "name": "cueApplied", "entries": [{"handles": [...]}]}
            print(event["name"], event["entries"])
```

`poll_events(timeout=0)` never blocks; with a timeout it waits up to that many seconds for the
first event. Events that arrive while you wait for the reply of a normal `send()` are queued and
returned by the next `poll_events()`.

`"onlyDiscrete"` pushes discrete changes immediately and leaves continuous values (positions) to
`pollMonitoring`.

## Subjects

From the Pixera API documentation:

| Subject | Entries |
|---|---|
| `clipAdded`, `clipChanged`, `clipRemoved` | `{"handles": [...]}` |
| `cueAdded`, `cueChanged`, `cueRemoved`, `cueApplied` | `{"handles": [...]}` |
| `timelineAdded`, `timelineRemoved` | `{"handles": [...]}` |
| `timelineTransport` | `handle` / `value` (transport mode) |
| `timelinePositions` | `handle` / `value` (time in frames) |
| `timelineCountdowns` | `handle` / `value` (frames) / `flag` (1 = to next cue, 2 = wait duration) |

Use `API.Utility.subscribeMonitoringSubject(name)` / `unsubscribeMonitoringSubject(name)` to choose.
