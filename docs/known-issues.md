# Known issues with PIXERA 26.1 R39 (API revision 481)

Found with `examples/smoke_test.py` against a real PIXERA 26.1 R39 on 2026-11-03 (two runs).

## Functions without return value reply with `1`

The API documentation shows replies without `result` for `null` functions
(`{"jsonrpc":"2.0", "id":3}`). PIXERA 26.1 R39 sends `"result": 1` instead, e.g. for
`Pixera.Utility.noop`. `send()` passes the result through, so these calls return `1`, not `None`.
Do not rely on the return value of functions documented as returning nothing.

`Pixera.Utility.pollMonitoring` returned `1` too while nothing was pending (default
event mode `"none"`). The documentation describes an array of subjects; expect `1` when there
is nothing to report.

## Errors come as a typed result, not as a JSON-RPC error

Calling a method that does not exist (`Pixera.Utility.doesNotExist`) gets no JSON-RPC `error`
object. Pixera sends a normal reply whose result marks an exception:

```json
{"id": 5, "jsonrpc": "2.0", "result": {"_pixc": {"type": 125, "typeName": "Exception"}}}
```

Since 0.481.2 `send()` recognises this and raises `PixeraError` (`code` 125, the full result in
`.data`). The reply carries no message, so the error does not say what went wrong.
`pixera.has_function(name)` (uses `Pixera.Utility.getHasFunction`) checks beforehand whether a
method exists.

## MultiUserMember methods reported as unknown

`getHasFunction` returns `false` for 14 of the 17 methods of `Pixera.LiveSystems.MultiUserMember`,
although the rev481 description lists them (and rev381 did already):

`closeEngine`, `ensureFileDistribution`, `getMacAddress`, `getPerformanceMonitoringValuesJson`,
`getPerformanceMonitoringValuesJsonEx`, `getState`, `getStructureJson`,
`resetCumulativePerformanceMonitoringValues`, `resetEngine`, `restartEngine`, `shutDown`,
`startEngine`, `triggerBackup`, `wakeUp`.

Only `getName`, `getIp` and `getInst` are reported as available.

Called directly on a real multi-user member (test run on 2026-11-03), `getName` works
(`"Office-Workstation-2"`), while `getState` and `getMacAddress` answer with the exception result
(`{"_pixc": {"type": 125, "typeName": "Exception"}}`, raised as `PixeraError` since 0.481.2).
So on PIXERA 26.1 R39 the 14 methods reported as unknown are most likely documented but not
implemented for multi-user members (two of them confirmed).
The functions stay in the library because they are part of the official description and may work
in later Pixera versions. Use the equivalent `LiveSystems.LiveSystem` methods for live systems;
those are reported as available.

All other functions of the library are reported as available (Ui and WebViews were not checked,
they are only available to plugins hosted inside Pixera).
