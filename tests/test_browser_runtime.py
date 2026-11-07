import threading

from backend.app.tools import browser


class FakePage:
    def is_closed(self):
        return False


class FakeContext:
    def __init__(self):
        self.pages = []
        self.closed = False

    def new_page(self):
        page = FakePage()
        self.pages.append(page)
        return page

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, context):
        self.context = context
        self.launches = []

    def launch_persistent_context(self, **kwargs):
        self.launches.append(kwargs)
        return self.context


class FakePlaywright:
    def __init__(self, context):
        self.chromium = FakeChromium(context)
        self.stopped = False

    def stop(self):
        self.stopped = True


def test_runtime_reuses_context_page_on_a_dedicated_thread(monkeypatch, tmp_path):
    profile_dir = tmp_path / "browser"
    monkeypatch.setattr(browser, "_ensure_profile_dir", lambda: profile_dir)
    context = FakeContext()
    playwright = FakePlaywright(context)
    factory_threads = []
    operation_threads = []
    runtime = browser._BrowserRuntime(
        playwright_factory=lambda: (
            factory_threads.append(threading.get_ident()) or playwright
        )
    )

    try:
        first_page = runtime.submit(
            lambda page: operation_threads.append(threading.get_ident()) or page
        ).result(timeout=2)
        second_page = runtime.submit(
            lambda page: operation_threads.append(threading.get_ident()) or page
        ).result(timeout=2)
    finally:
        runtime.close()

    assert first_page is second_page
    assert len(factory_threads) == 1
    assert operation_threads == factory_threads * 2
    assert len(playwright.chromium.launches) == 1
    assert playwright.chromium.launches[0]["user_data_dir"] == str(profile_dir)
    assert context.closed
    assert playwright.stopped
