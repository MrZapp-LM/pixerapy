"""Check PixeraPy against a running Pixera. Read-only: nothing in the project is changed.

    python examples/smoke_test.py 192.168.1.10 1400
    python examples/smoke_test.py 192.168.1.10 1400 --dl-port 1401 --http-port 8080

The port must be a "JSON/TCP" API access point (Pixera: Settings > API). The optional ports
test the "JSON/TCP (dl)" and "HTTP/TCP" access points too.
"""

import argparse
import inspect
import json
import time

from PixeraPy import API, API_REVISION, Pixera, PixeraError

results = []

# Documented in rev481 but reported as unknown by getHasFunction on PIXERA 26.1 R39 (see docs/known-issues.md).
KNOWN_UNREPORTED = {
    f"Pixera.LiveSystems.MultiUserMember.{name}"
    for name in (
        "closeEngine", "ensureFileDistribution", "getMacAddress", "getPerformanceMonitoringValuesJson",
        "getPerformanceMonitoringValuesJsonEx", "getState", "getStructureJson",
        "resetCumulativePerformanceMonitoringValues", "resetEngine", "restartEngine", "shutDown",
        "startEngine", "triggerBackup", "wakeUp",
    )
}


def check(name, func):
    try:
        detail = func()
        results.append((name, True, detail))
        print(f"OK      {name}" + (f": {detail}" if detail else ""))
    except Exception as error:  # noqa: BLE001 - report everything
        results.append((name, False, repr(error)))
        print(f"FEHLER  {name}: {error!r}")


def all_methods(scope=API, seen=None):
    """Every Pixera method name the library knows, e.g. 'Pixera.Screens.Screen.getName'."""
    seen = set() if seen is None else seen
    for name, value in vars(scope).items():
        if name.startswith("_"):
            continue
        if isinstance(value, type):
            if value not in seen:
                seen.add(value)
                yield from all_methods(value, seen)
        elif isinstance(value, staticmethod):
            func = value.__func__
            yield func(*[0] * len(inspect.signature(func).parameters))[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ip")
    parser.add_argument("port", type=int)
    parser.add_argument("--dl-port", type=int)
    parser.add_argument("--http-port", type=int)
    args = parser.parse_args()

    pixera = Pixera(args.ip, args.port, timeout=5)

    check("Verbindung JSON/TCP (outputDebug)", lambda: pixera.send(API.Utility.outputDebug("PixeraPy smoke test")))

    def revision():
        rev = pixera.send(API.Utility.getApiRevision())
        if rev != API_REVISION:
            return f"Pixera hat Revision {rev}, die Lib {API_REVISION} (kein Fehler, nur zur Info)"
        return f"Revision {rev}"
    check("API-Revision", revision)

    def noop():
        # Pixera 26.1 R39 answers with result 1 instead of leaving result out; both are fine.
        reply = pixera.send(API.Utility.noop(), raw_output=True)
        assert "error" not in reply, f"Fehler von Pixera: {reply}"
        return f"Antwort: {json.dumps(reply)}"
    check("Funktion ohne Rückgabewert (noop)", noop)

    def unknown():
        assert pixera.has_function("Pixera.Utility.doesNotExist") is False, "getHasFunction meldet die Funktion als vorhanden"
        try:
            reply = pixera.send(["Pixera.Utility.doesNotExist"])
        except PixeraError as error:
            return f"getHasFunction -> False; PixeraError {error.code}"
        raise AssertionError(f"kein Fehler, Antwort: {reply!r}")
    check("Unbekannte Funktion", unknown)

    def large():
        return f"{len(pixera.send(API.Utility.getLicenseJson()))} Zeichen"
    check("Lange Antwort (getLicenseJson)", large)

    def screens():
        handles = pixera.send(API.Screens.getScreens())
        names = [pixera.send(API.Screens.Screen.getName(h)) for h in handles[:5]]
        return f"{len(handles)} Screens {names}"
    check("Handles (getScreens, Screen.getName)", screens)

    def timelines():
        handles = pixera.send(API.Timelines.getTimelines())
        names = [pixera.send(API.Timelines.Timeline.getName(h)) for h in handles[:5]]
        return f"{len(handles)} Timelines {names}"
    check("Timelines", timelines)

    check("Neue rev481-Funktion (getScreenGroupNames)",
          lambda: pixera.send(API.Screens.getScreenGroupNames()))

    def optional_param():
        projectors = pixera.send(API.Projectors.getProjectors())
        if not projectors:
            return "übersprungen, keine Projektoren im Projekt"
        return f"Projector.getOutput ohne index -> {pixera.send(API.Projectors.Projector.getOutput(projectors[0]))}"
    check("Optionaler Parameter weggelassen", optional_param)

    def struct_return():
        handles = pixera.send(API.Screens.getScreens())
        if not handles:
            return "übersprungen, keine Screens im Projekt"
        return pixera.send(API.Screens.Screen.getPosition(handles[0]))
    check("Struct-Rückgabe (Screen.getPosition)", struct_return)

    def keep_alive():
        with Pixera(args.ip, args.port, timeout=5) as client:
            start = time.perf_counter()
            for i in range(50):
                assert client.send(API.Utility.outputDebug(str(i))) == str(i)
            return f"50 Aufrufe auf einer Verbindung in {time.perf_counter() - start:.2f} s"
    check("Persistente Verbindung", keep_alive)

    def monitoring():
        with Pixera(args.ip, args.port, timeout=5) as client:
            client.send(API.Utility.setMonitoringEventMode("none"))
            polled = client.send(API.Utility.pollMonitoring(), raw_output=True)
            client.send(API.Utility.setMonitoringEventMode("all"))
            events = client.poll_events(timeout=2.0)
            return f"pollMonitoring -> {json.dumps(polled)[:200]}; {len(events)} Events in 2 s (0 ist ok, wenn nichts läuft)"
    check("Monitoring", monitoring)

    def multi_user_member():
        members = pixera.send(API.LiveSystems.getMultiUserMembers())
        if not members:
            return "übersprungen, keine Multi-User-Mitglieder"
        member = members[0]
        return {
            "getName": pixera.send(API.LiveSystems.MultiUserMember.getName(member), raw_output=True),
            "getState": pixera.send(API.LiveSystems.MultiUserMember.getState(member), raw_output=True),
            "getMacAddress": pixera.send(API.LiveSystems.MultiUserMember.getMacAddress(member), raw_output=True),
        }
    check("MultiUserMember direkt aufrufen", multi_user_member)

    def has_functions():
        names = sorted(set(all_methods()))
        missing = []
        with Pixera(args.ip, args.port, timeout=5) as client:
            for name in names:
                if not client.send(API.Utility.getHasFunction(name)):
                    missing.append(name)
        # Ui and WebViews are only available to plugins hosted inside Pixera.
        missing = [name for name in missing if not name.startswith(("Pixera.Ui.", "Pixera.WebViews."))]
        known = [name for name in missing if name in KNOWN_UNREPORTED]
        missing = [name for name in missing if name not in KNOWN_UNREPORTED]
        if known:
            print(f"        Hinweis: {len(known)} MultiUserMember-Methoden meldet Pixera 26.1 R39 als unbekannt (bekannt, siehe docs/known-issues.md)")
        if missing:
            raise AssertionError(f"{len(missing)} von {len(names)} Funktionen kennt Pixera nicht: {missing[:20]}")
        return f"alle {len(names)} Funktionen bekannt (Ui/WebViews nicht geprüft)"
    check("Alle Funktionen der Lib (getHasFunction)", has_functions)

    if args.dl_port:
        check("Verbindung JSON/TCP (dl)",
              lambda: Pixera(args.ip, args.dl_port, protocol="TCP_DL", timeout=5).send(API.Utility.outputDebug("dl")))
    if args.http_port:
        check("Verbindung HTTP",
              lambda: Pixera(args.ip, args.http_port, protocol="HTTP", timeout=5).send(API.Utility.outputDebug("http")))

    failed = [name for name, ok, _ in results if not ok]
    print()
    print(f"{len(results) - len(failed)} OK, {len(failed)} FEHLER")
    with open("smoke_test_result.json", "w", encoding="utf-8") as file:
        json.dump([{"check": n, "ok": ok, "detail": d} for n, ok, d in results], file, indent=2, default=str)
    print("Details in smoke_test_result.json")


if __name__ == "__main__":
    main()
