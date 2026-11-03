# Known issues with PIXERA 26.1 R39 (API revision 481)

Found with `examples/smoke_test.py` against a real PIXERA 26.1 R39 on 2026-11-03.

## Functions without return value reply with `1`

The API documentation shows replies without `result` for `null` functions
(`{"jsonrpc":"2.0", "id":3}`). PIXERA 26.1 R39 sends `"result": 1` instead, e.g. for
`Pixera.Utility.noop`. `send()` passes the result through, so these calls return `1`, not `None`.
Do not rely on the return value of functions documented as returning nothing.

`Pixera.Utility.pollMonitoring` returned `1` too while nothing was pending (default
event mode `"none"`). The documentation describes an array of subjects; expect `1` when there
is nothing to report.

## Unknown functions do not raise an error

Calling a method that does not exist (`Pixera.Utility.doesNotExist`) gets no JSON-RPC error
reply, so `send()` does not raise `PixeraError`. Typos in method names therefore fail silently.
Check with `pixera.has_function("Pixera.Timelines.Timeline.play")` (uses
`Pixera.Utility.getHasFunction`) when in doubt. `PixeraError` is still raised whenever Pixera
does send an error object.

## MultiUserMember methods reported as unknown

`getHasFunction` returns `false` for 14 of the 17 methods of `Pixera.LiveSystems.MultiUserMember`,
although the rev481 description lists them (and rev381 did already):

`closeEngine`, `ensureFileDistribution`, `getMacAddress`, `getPerformanceMonitoringValuesJson`,
`getPerformanceMonitoringValuesJsonEx`, `getState`, `getStructureJson`,
`resetCumulativePerformanceMonitoringValues`, `resetEngine`, `restartEngine`, `shutDown`,
`startEngine`, `triggerBackup`, `wakeUp`.

Only `getName`, `getIp` and `getInst` are reported as available. The functions stay in the library
because they are part of the official description. Whether they work when called directly is not
yet known (the test project had no multi-user members; the smoke test calls `getName`, `getState`
and `getMacAddress` on the first member when one exists). The equivalent methods on
`LiveSystems.LiveSystem` are reported as available.

All other functions of the library are reported as available (Ui and WebViews were not checked,
they are only available to plugins hosted inside Pixera).
