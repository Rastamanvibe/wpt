import os
from distutils.spawn import find_executable

import psutil

from .base import Browser, ExecutorBrowser, require_arg
from .base import get_timeout_multiplier   # noqa: F401
from ..webdriver_server import SafariDriverServer
from ..executors import executor_kwargs as base_executor_kwargs
from ..executors.executorwebdriver import (WebDriverTestharnessExecutor,  # noqa: F401
                                           WebDriverRefTestExecutor,  # noqa: F401
                                           WebDriverCrashtestExecutor)  # noqa: F401
from ..executors.executorsafari import SafariDriverWdspecExecutor  # noqa: F401


__wptrunner__ = {"product": "safari",
                 "check_args": "check_args",
                 "browser": "SafariBrowser",
                 "executor": {"testharness": "WebDriverTestharnessExecutor",
                              "reftest": "WebDriverRefTestExecutor",
                              "wdspec": "SafariDriverWdspecExecutor",
                              "crashtest": "WebDriverCrashtestExecutor"},
                 "browser_kwargs": "browser_kwargs",
                 "executor_kwargs": "executor_kwargs",
                 "env_extras": "env_extras",
                 "env_options": "env_options",
                 "timeout_multiplier": "get_timeout_multiplier"}


def check_args(**kwargs):
    require_arg(kwargs, "webdriver_binary")


def browser_kwargs(logger, test_type, run_info_data, config, **kwargs):
    return {"webdriver_binary": kwargs["webdriver_binary"],
            "webdriver_args": kwargs.get("webdriver_args"),
            "kill_safari": kwargs.get("kill_safari", False)}


def executor_kwargs(logger, test_type, server_config, cache_manager, run_info_data,
                    **kwargs):
    executor_kwargs = base_executor_kwargs(test_type, server_config,
                                           cache_manager, run_info_data, **kwargs)
    executor_kwargs["close_after_done"] = True
    executor_kwargs["capabilities"] = {}
    if test_type == "testharness":
        executor_kwargs["capabilities"]["pageLoadStrategy"] = "eager"
    if kwargs["binary"] is not None:
        raise ValueError("Safari doesn't support setting executable location")

    return executor_kwargs


def env_extras(**kwargs):
    return []


def env_options():
    return {}


class SafariBrowser(Browser):
    """Safari is backed by safaridriver, which is supplied through
    ``wptrunner.webdriver.SafariDriverServer``.
    """

    def __init__(self, logger, webdriver_binary, webdriver_args=None, kill_safari=False):
        """Creates a new representation of Safari.  The `webdriver_binary`
        argument gives the WebDriver binary to use for testing. (The browser
        binary location cannot be specified, as Safari and SafariDriver are
        coupled.) If `kill_safari` is True, then `Browser.stop` will stop Safari."""
        Browser.__init__(self, logger)
        self.server = SafariDriverServer(self.logger,
                                         binary=webdriver_binary,
                                         args=webdriver_args)
        if "/" not in webdriver_binary:
            wd_path = find_executable(webdriver_binary)
        else:
            wd_path = webdriver_binary
        if os.path.samefile(wd_path, "/usr/bin/safaridriver"):
            self.safari_path = "/Applications/Safari.app/Contents/MacOS/Safari"
        else:
            self.safari_path = os.path.join(os.path.dirname(wd_path), "Safari")
        logger.debug("wd_path: %s" % wd_path)
        logger.debug("safari_path: %s" % self.safari_path)

        self.kill_safari = kill_safari

    def start(self, **kwargs):
        self.server.start(block=False)

    def stop(self, force=False):
        self.server.stop(force=force)

        if self.kill_safari:
            self.logger.debug("Going to stop Safari")
            for proc in psutil.process_iter(attrs=["exe"]):
                if proc.info["exe"] is not None and os.path.samefile(proc.info["exe"], self.safari_path):
                    self.logger.debug("Stopping Safari %s" % proc.pid)
                    try:
                        proc.terminate()
                        try:
                            proc.wait(10)
                        except psutil.TimeoutExpired:
                            proc.kill()
                    except psutil.NoSuchProcess:
                        pass

    def pid(self):
        return self.server.pid

    def is_alive(self):
        # TODO(ato): This only indicates the driver is alive,
        # and doesn't say anything about whether a browser session
        # is active.
        return self.server.is_alive()

    def cleanup(self):
        self.stop()

    def executor_browser(self):
        return ExecutorBrowser, {"webdriver_url": self.server.url}
