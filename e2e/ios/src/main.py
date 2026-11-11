"""pyios-firebase end-to-end test app.

Runs the Firestore suite against the local Firestore emulator through the
real Firebase iOS SDK, shows the results on screen, prints them (prefix
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
RESULTS = os.path.join(os.path.expanduser("~/Documents"), "pyios-e2e-results.json")


def configure_firebase() -> None:
    from pyios_firebase.firestore import Firestore
    from pyios_firebase.util import objc_class

    options = objc_class("FIROptions").alloc().initWithGoogleAppID_GCMSenderID_(
        "1:1234567890:ios:0123456789abcdef", "1234567890"
    )
    options.projectID = PROJECT_ID
    options.APIKey = "AIzaSyD-emulator-only-not-a-real-key-000"
    objc_class("FIRApp").configureWithOptions_(options)

    host, port = EMULATOR_HOST.rsplit(":", 1)
    Firestore.firestore().use_emulator(host, int(port))


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
            from firestore_tests import RUN_ID, TESTS
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
        Runner(
            TESTS,
            self.progress,
            lambda report: self.finish(report, dumps),
            on_test_start=self.test_started,
        ).start()

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
        summary = f"PYIOS-E2E DONE passed={report['passed']} failed={report['failed']}"
        print(summary, flush=True)
        for result in report["results"]:
            if not result["ok"]:
                print(f"PYIOS-E2E FAILED {result['name']}:\n{result['detail']}", flush=True)
        lines = getattr(self, "lines", [])
        self.label.text = "\n".join([*lines, "", summary.replace("PYIOS-E2E ", "")])


if __name__ == "__main__":
    E2EApp().run()
    sys.exit(0)
