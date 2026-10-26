import importlib.util
import inspect
import subprocess
import sys
from pathlib import Path

from PixeraPy import API, API_REVISION
from PixeraPy import api_functions

ROOT = Path(__file__).resolve().parent.parent

# Functions whose signature changed in the Pixera API after revision 381.
CHANGED_SINCE_381 = {
    "LiveSystem.applyUsagePreset",  # name parameter removed (see applyUsagePresetWithName)
    "Timeline.createCue",  # new required cueLayerHandle
    "Timeline.createPauseCueBeforeSelectedClips",  # new required cueLayerHandle
    "Clip.createPauseCueBeforeClip",  # new required cueLayerHandle
}
REMOVED_SINCE_381 = {"Timeline.CurrentTime"}


def load_rev381():
    spec = importlib.util.spec_from_file_location("api_rev381", ROOT / "tests" / "fixtures" / "api_functions_rev381.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.API


def iter_callables(api):
    for name, value in vars(api).items():
        if name.startswith("_"):
            continue
        if isinstance(value, type):
            for method, _ in vars(value).items():
                if not method.startswith("_"):
                    yield f"{name}.{method}", getattr(value, method)
        else:
            yield name, getattr(api, name)


def resolve(path):
    obj = API
    for part in path.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return obj


def test_revision():
    assert API_REVISION == 481


def test_old_calls_build_identical_requests():
    """Everything that worked with PixeraPy 0.381/0.461 still builds the same request."""
    for path, old in iter_callables(load_rev381()):
        if path in REMOVED_SINCE_381:
            continue
        new = resolve(path)
        assert new is not None, f"{path} disappeared"
        if path in CHANGED_SINCE_381:
            continue
        args = list(range(len(inspect.signature(old).parameters)))
        assert new(*args) == old(*args), path


def test_instance_access_still_works():
    api = API()
    assert api.getScreens() == ["Pixera.Screens.getScreens", [], []]
    assert api.Screen.getName(7) == ["Pixera.Screens.Screen.getName", ["handle"], [7]]


def test_namespaced_access():
    assert API.Screens.Screen.getName(7)[0] == "Pixera.Screens.Screen.getName"
    assert API.Direct.Screen.setPosition(1, 2.0)[0] == "Pixera.Direct.Screen.setPosition"
    assert API.Ui.Control.setControlPage("Main") == ["Pixera.Ui.Control.setControlPage", ["pageName"], ["Main"]]
    assert API.Settings.SettingsGeneral.getFadeToTimeDuration()[0] == "Pixera.Settings.SettingsGeneral.getFadeToTimeDuration"


def test_new_rev481_functions_exist():
    assert API.Timelines.Timeline.applyCueWithNumberString(1, "1.2")[0] == "Pixera.Timelines.Timeline.applyCueWithNumberString"
    assert API.Screens.getScreenGroups()[0] == "Pixera.Screens.getScreenGroups"
    assert API.Layer.setOpacity(3, 0.5, 1000) == ["Pixera.Timelines.Layer.setOpacity", ["handle", "value", "fadeTimeMs"], [3, 0.5, 1000]]
    assert API.Layer.setOpacity(3, 0.5) == ["Pixera.Timelines.Layer.setOpacity", ["handle", "value"], [3, 0.5]]


def test_generated_file_is_up_to_date(tmp_path):
    out, ref = tmp_path / "api.py", tmp_path / "ref.md"
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "generate_api.py"), str(ROOT / "api" / "pixera_api_comments_rev481.txt"),
         "--out", str(out), "--reference", str(ref)],
        check=True, capture_output=True,
    )
    assert out.read_text(encoding="utf-8") == Path(api_functions.__file__).read_text(encoding="utf-8")
    assert ref.read_text(encoding="utf-8") == (ROOT / "docs" / "api-reference.md").read_text(encoding="utf-8")
