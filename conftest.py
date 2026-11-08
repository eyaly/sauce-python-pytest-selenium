import logging
import os
import time

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.safari.options import Options as SafariOptions

from config.capabilities import CAPABILITIES

log = logging.getLogger("sauce")

FAILURES_DIR = os.path.join("reports", "failures")

SAUCE_REGIONS = {
    "us": {
        "hub": "https://ondemand.us-west-1.saucelabs.com/wd/hub",
        "app": "https://app.saucelabs.com",
    },
    "eu": {
        "hub": "https://ondemand.eu-central-1.saucelabs.com/wd/hub",
        "app": "https://app.eu-central-1.saucelabs.com",
    },
}


def sauce_region(region):
    """Accepts us / eu / us-west-1 / eu-central-1 / US_WEST / EU_CENTRAL (case-insensitive)."""
    key = region.lower()[:2]
    if key not in SAUCE_REGIONS:
        raise pytest.UsageError(f"Unknown Sauce region '{region}'. Use 'us' or 'eu'.")
    return SAUCE_REGIONS[key]


OPTIONS_CLASSES = {
    "chrome": ChromeOptions,
    "safari": SafariOptions,
    "firefox": FirefoxOptions,
    "edge": EdgeOptions,
}


def pytest_configure(config):
    # Set the build name once in the main process; xdist workers inherit the env var,
    # so all parallel executions are grouped under the same Sauce Labs build.
    if not hasattr(config, "workerinput"):
        os.environ.setdefault("SAUCE_BUILD_NAME", f"sauce-python-pytest-selenium-{time.strftime('%Y%m%d-%H%M%S')}")


def pytest_addoption(parser):
    parser.addoption(
        "--browser",
        action="store",
        default="all",
        help=f"Browser(s) to run on: {', '.join(CAPABILITIES)}, or all (comma separated allowed). Default: all",
    )
    parser.addoption(
        "--region",
        action="store",
        default=os.environ.get("SAUCE_REGION", "eu"),
        help="Sauce Labs data center: us or eu (also via SAUCE_REGION env var). Default: eu",
    )


def pytest_generate_tests(metafunc):
    """Parametrize every test that uses the `driver` fixture by browser.

    Called once per test function. N tests x M browsers = N*M test items -> N*M Sauce Labs sessions.
    """
    if "driver" in metafunc.fixturenames:
        selected = metafunc.config.getoption("--browser")
        browsers = list(CAPABILITIES) if selected == "all" else [b.strip() for b in selected.split(",")]
        unknown = set(browsers) - set(CAPABILITIES)
        if unknown:
            raise pytest.UsageError(f"Unknown browser(s): {unknown}. Available: {list(CAPABILITIES)}")
        metafunc.parametrize("browser_name", browsers, ids=browsers)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item):
    """Store each phase's report on the item so the driver fixture can report pass/fail to Sauce Labs."""
    report = yield
    setattr(item, f"rep_{report.when}", report)
    job_url = dict(item.user_properties).get("sauce_job_url")
    if report.failed and job_url:
        _add_job_url_to_failure(report, job_url)
    return report


def _add_job_url_to_failure(report, job_url):
    """Start the failure message with the Sauce Labs job link.

    The link then shows in the JUnit <failure message="..."> (what CI tools display as
    the error message) and in pytest's short summary.
    """
    line = f"Sauce Labs job: {job_url}"
    crash = getattr(report.longrepr, "reprcrash", None)
    if crash is not None:
        crash.message = f"{line}\n{crash.message}"
    else:
        report.longrepr = f"{line}\n\n{report.longrepr}"


@pytest.fixture
def driver(request, browser_name):
    username = os.environ.get("SAUCE_USERNAME")
    access_key = os.environ.get("SAUCE_ACCESS_KEY")
    if not username or not access_key:
        pytest.exit("Please set SAUCE_USERNAME and SAUCE_ACCESS_KEY environment variables", returncode=1)

    caps = CAPABILITIES[browser_name]
    options = OPTIONS_CLASSES[browser_name]()
    options.browser_version = caps["browserVersion"]
    options.platform_name = caps["platformName"]
    options.set_capability(
        "sauce:options",
        {
            "username": username,
            "accessKey": access_key,
            "name": request.node.originalname,  # test function name, without the [browser] suffix
            "build": os.environ["SAUCE_BUILD_NAME"],
            "tags": ["pytest", "selenium", browser_name],
        },
    )

    region = sauce_region(request.config.getoption("--region"))
    browser = webdriver.Remote(command_executor=region["hub"], options=options)
    browser.implicitly_wait(10)

    # Sauce job link: logged (captured into the JUnit report via junit_logging=all)
    # and stored as a JUnit <property> on the test case.
    job_url = f"{region['app']}/tests/{browser.session_id}"
    log.info("Sauce Labs job: %s", job_url)
    request.node.user_properties.append(("sauce_job_url", job_url))

    yield browser

    # Report pass/fail to Sauce Labs
    rep_call = getattr(request.node, "rep_call", None)
    passed = bool(rep_call and rep_call.passed)
    try:
        if not passed:
            _save_failure_screenshot(browser, request.node.name)
            # Show the failure reason in the Sauce Labs job's command list
            reason = _failure_reason(rep_call or getattr(request.node, "rep_setup", None))
            browser.execute_script(f"sauce:context=Test failed: {reason}")
        browser.execute_script(f"sauce:job-result={'passed' if passed else 'failed'}")
    finally:
        browser.quit()


def _failure_reason(report, max_length=500):
    """One-line failure reason from a pytest report, e.g. "AssertionError: assert 'x' in 'y'"."""
    if report is None:
        return "unknown reason"
    crash = getattr(report.longrepr, "reprcrash", None)
    message = crash.message if crash is not None else str(report.longrepr or "unknown reason")
    # Skip the "Sauce Labs job: <url>" line that pytest_runtest_makereport adds, and keep only
    # the first line of the error (pytest's "+ where ..." explanation lines follow it)
    lines = [line.strip() for line in message.splitlines()
             if line.strip() and not line.startswith("Sauce Labs job:")]
    reason = lines[0] if lines else "unknown reason"
    return reason if len(reason) <= max_length else reason[: max_length - 3] + "..."


def _save_failure_screenshot(browser, test_name):
    """Save a screenshot to reports/failures/ (published by the CI pipeline as an artifact).

    test_name is e.g. "test_valid_login[chrome]" -> reports/failures/test_valid_login-chrome.png
    """
    safe_name = test_name.replace("[", "-").replace("]", "")
    path = os.path.join(FAILURES_DIR, f"{safe_name}.png")
    try:
        os.makedirs(FAILURES_DIR, exist_ok=True)
        browser.save_screenshot(path)
        log.info("Failure screenshot: %s", path)
    except Exception as e:  # never let a screenshot problem hide the real test failure
        log.warning("Could not save failure screenshot: %s", e)
