"""pyios-firebase end-to-end test app.

Runs the Firestore, Auth, Functions, Storage, Remote Config and App Check
suites against the local Firebase emulators through the real Firebase iOS SDK, shows the results on screen, prints them (prefix
``PYIOS-E2E``), and writes them to ``Documents/pyios-e2e-results.json``.

No GoogleService-Info.plist: Firebase is configured in code for the offline
``demo-pyios-firebase`` project, which only the emulator serves.
"""

import os
import sys
import traceback

from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

PROJECT_ID = "demo-pyios-firebase"
EMULATOR_HOST = os.environ.get("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
AUTH_EMULATOR_HOST = os.environ.get("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
FUNCTIONS_EMULATOR_HOST = "127.0.0.1:5001"
STORAGE_EMULATOR_HOST = os.environ.get("FIREBASE_STORAGE_EMULATOR_HOST", "127.0.0.1:9199")
STORAGE_BUCKET = "demo-pyios-firebase.appspot.com"
RESULTS = os.path.join(os.path.expanduser("~/Documents"), "pyios-e2e-results.json")


def configure_firebase() -> None:
    from app_check_tests import E2EAppCheckProvider
    from pyios_firebase import app_check
    from pyios_firebase.auth import Auth
    from pyios_firebase.firestore import Firestore
    from pyios_firebase.functions import Functions
    from pyios_firebase.storage import Storage
    from pyios_firebase.util import objc_class

    # App Check: a Python custom provider, set before configure as it must be
    app_check.use_custom_provider(E2EAppCheckProvider.shared())

    options = objc_class("FIROptions").alloc().initWithGoogleAppID_GCMSenderID_(
        "1:1234567890:ios:0123456789abcdef", "1234567890"
    )
    options.projectID = PROJECT_ID
    # Firebase Installations (used by Remote Config) checks the format: 39 characters
    options.APIKey = "AIzaSyD-emulator-only-not-a-real-key-00"
    options.storageBucket = STORAGE_BUCKET
    objc_class("FIRApp").configureWithOptions_(options)

    host, port = EMULATOR_HOST.rsplit(":", 1)
    Firestore.firestore().use_emulator(host, int(port))
    host, port = AUTH_EMULATOR_HOST.rsplit(":", 1)
    Auth.auth().use_emulator(host, int(port))
    host, port = FUNCTIONS_EMULATOR_HOST.rsplit(":", 1)
    Functions.functions().use_emulator(host, int(port))
    Functions.functions("europe-west1").use_emulator(host, int(port))
    host, port = STORAGE_EMULATOR_HOST.rsplit(":", 1)
    Storage.storage().use_emulator(host, int(port))


class E2EApp(App):
    def build(self):
        Window.clearcolor = (1, 1, 1, 1)
        self.label = Label(
            text="pyios-firebase e2e\nrunning…",
            color=(0, 0, 0, 1),
            font_size="13sp",
            halign="left",
            valign="top",
            size_hint_y=None,
            padding=(dp(16), dp(64)),  # below the status bar
        )
        self.label.bind(
            width=lambda *_: setattr(self.label, "text_size", (self.label.width, None)),
            texture_size=lambda *_: setattr(self.label, "height", self.label.texture_size[1]),
        )
        scroll = ScrollView()
        scroll.add_widget(self.label)
        return scroll

    def on_start(self):
        try:
            os.remove(RESULTS)
        except FileNotFoundError:
            pass
        try:
            configure_firebase()
            from app_check_tests import TESTS as APP_CHECK_TESTS
            from auth_tests import TESTS as AUTH_TESTS
            from firestore_tests import RUN_ID
            from firestore_tests import TESTS as FIRESTORE_TESTS
            from functions_tests import TESTS as FUNCTIONS_TESTS
            from remote_config_tests import TESTS as REMOTE_CONFIG_TESTS
            from storage_tests import TESTS as STORAGE_TESTS

            TESTS = (
                FIRESTORE_TESTS + AUTH_TESTS + FUNCTIONS_TESTS + STORAGE_TESTS
                + REMOTE_CONFIG_TESTS + APP_CHECK_TESTS
            )
            from runner import Runner, dumps
        except Exception:  # noqa: BLE001
            self.finish({"passed": 0, "failed": 1, "results": [
                {"name": "setup", "ok": False, "detail": traceback.format_exc(), "seconds": 0}]})
            return
        print(
            f"PYIOS-E2E START run={RUN_ID} tests={len(TESTS)} emulator={EMULATOR_HOST}",
            flush=True,
        )
        self.lines = [f"pyios-firebase e2e — run {RUN_ID}", ""]
        self.running = ""
        runner = Runner(
            TESTS,
            self.progress,
            lambda report: self.finish(report, dumps),
            on_test_start=self.test_started,
        )
        self.warm_up(runner.start)

    def warm_up(self, then):
        """One Firestore read before the tests: the emulator's first connection
        can take several seconds, which must not count against the first test."""
        from kivy.clock import Clock

        from pyios_firebase.firestore import Firestore

        state = {"started": False}

        def start(*_args):
            if not state["started"]:
                state["started"] = True
                print(f"PYIOS-E2E WARM {'timed out' if _args == ('timeout',) else 'ok'}", flush=True)
                then()

        Firestore.firestore().document_with_path("e2e_warmup/ping").get_document(
            lambda snapshot, error: Clock.schedule_once(lambda dt: start(), 0)
        )
        Clock.schedule_once(lambda dt: start("timeout"), 60)

    def show(self):
        running = ["", f"▶ {self.running}"] if self.running else []
        self.label.text = "\n".join([*self.lines, *running])

    def test_started(self, name):
        self.running = name
        self.show()

    def progress(self, line):
        self.running = ""
        self.lines.append(line.replace("PYIOS-E2E ", ""))
        self.show()

    def finish(self, report, dumps=None):
        import json

        text = (dumps or (lambda r: json.dumps(r, indent=2)))(report)
        with open(RESULTS + ".tmp", "w") as f:
            f.write(text)
        os.replace(RESULTS + ".tmp", RESULTS)  # the host polls for this file
        summary = (
            f"PYIOS-E2E DONE passed={report['passed']} failed={report['failed']}"
            f" skipped={report.get('skipped', 0)}"
        )
        print(summary, flush=True)
        for result in report["results"]:
            if not result["ok"]:
                print(f"PYIOS-E2E FAILED {result['name']}:\n{result['detail']}", flush=True)
        lines = getattr(self, "lines", [])
        self.label.text = "\n".join([*lines, "", summary.replace("PYIOS-E2E ", "")])


if __name__ == "__main__":
    E2EApp().run()
    sys.exit(0)
