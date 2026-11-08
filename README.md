# sauce-python-pytest-selenium

PyTest + Selenium + Sauce Labs boilerplate for desktop browsers.

A minimal PyTest + Selenium framework that runs web tests on Sauce Labs desktop browser VMs.
No page objects — just a `conftest.py` that creates the remote driver and one test file.

Tests run against [www.saucedemo.com](https://www.saucedemo.com) on:

| `--browser` | Browser | Platform   |
|-------------|---------|------------|
| `chrome`  | Chrome (latest)  | Windows 11 |
| `safari`  | Safari (latest)  | macOS 13   |
| `firefox` | Firefox (latest) | macOS 13   |
| `edge`    | Edge (latest)    | Windows 11 |

## Project structure

```
.
├── ci/
│   └── sauce_summary.py    # Azure DevOps: adds a "Sauce Labs" job-link table to the run Summary page
├── config/
│   └── capabilities.py     # Browser/OS capabilities (Chrome, Safari, Firefox, Edge)
├── tests/
│   └── test_saucedemo.py   # 3 test cases
├── conftest.py             # Driver fixture, --browser / --region options, Sauce job status
├── pytest.ini
├── requirements.txt
└── LICENSE
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export SAUCE_USERNAME=<your username>
export SAUCE_ACCESS_KEY=<your access key>
```

## How the parallel run works

`conftest.py` parametrizes every test that uses the `driver` fixture by browser.
With 3 tests and 2 browsers (`--browser chrome,safari`), pytest collects **6 test items**:

```
tests/test_saucedemo.py::test_valid_login[chrome]
tests/test_saucedemo.py::test_valid_login[safari]
tests/test_saucedemo.py::test_locked_out_user[chrome]
tests/test_saucedemo.py::test_locked_out_user[safari]
tests/test_saucedemo.py::test_missing_username[chrome]
tests/test_saucedemo.py::test_missing_username[safari]
```

Each item opens its own Sauce Labs session. [`pytest-xdist`](https://pypi.org/project/pytest-xdist/)
with `-n 6` runs the 6 items on 6 workers at the same time:

```
worker 1 -> Chrome  (Windows 11) -> test_valid_login
worker 2 -> Chrome  (Windows 11) -> test_locked_out_user
worker 3 -> Chrome  (Windows 11) -> test_missing_username
worker 4 -> Safari  (macOS 13)   -> test_valid_login
worker 5 -> Safari  (macOS 13)   -> test_locked_out_user
worker 6 -> Safari  (macOS 13)   -> test_missing_username
```

All executions are grouped under the same Sauce Labs build. Without `--browser`, every
browser in `config/capabilities.py` is used: 3 tests x 4 browsers = 12 executions (`-n 12`).

## conftest.py execution order

pytest calls these functions itself, in this order (without `-n`, 3 tests x 2 browsers):

```
pytest_addoption          1×   declares --browser / --region
pytest_configure          1×   sets SAUCE_BUILD_NAME
pytest_generate_tests     3×   once per test function → creates 6 runs (reads --browser)
driver                    6×   once per run (reads --region, opens/closes the Sauce session)
pytest_runtest_makereport 18×  3 per run (saves results, adds job link on failure)
```

With `-n 6`, each worker is a separate process, so the first three run in every process
(`pytest_addoption` and `pytest_configure` 7× — main process + 6 workers, `pytest_generate_tests` 18×).
Only the main process sets the build name; workers inherit it. `driver` is still called exactly
6 times in total — once per run, one per worker.

## Run

```bash
# See what will run (no Sauce sessions are started)
pytest --collect-only -q

# All 4 browsers: 12 executions in parallel (each VM runs 1 test)
pytest -n 12

# Chrome + Safari: 6 executions in parallel
pytest -n 6 --browser chrome,safari

# One browser: 3 executions in parallel
pytest -n 3 --browser firefox

# Sequential (no parallelism)
pytest

# Run in the US data center (default: eu)
pytest -n 12 --region us

# Custom build name
SAUCE_BUILD_NAME="my-build" pytest -n 12
```

Tip: `-n auto` uses one worker per CPU core; set `-n` to the number of executions you
want running at once (limited by your Sauce Labs concurrency).

## JUnit report

Every run writes `reports/junit.xml` (configured in `pytest.ini`), also when running in
parallel with `-n` (xdist merges the results). For each test case the report contains the
Sauce Labs job link:

- as a `<property name="sauce_job_url">` (requires `junit_family = xunit1`)
- in the captured log (`junit_logging = all`)
- at the start of the `<failure message>` when a test fails, so CI tools that show the
  failure message show the link too

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--browser` | `all` | `chrome`, `safari`, `firefox`, `edge`, `all`, or comma separated (`chrome,safari`) |
| `--region`  | `eu`  | `us` (us-west-1) or `eu` (eu-central-1). Also via `SAUCE_REGION` env var (`EU_CENTRAL`, `eu-central-1`, etc. also work) |

## Adding a browser

Add an entry to `config/capabilities.py` and map the same key to its Selenium options class
in `OPTIONS_CLASSES` in `conftest.py`. Every test automatically runs on it.

## License

[MIT](LICENSE)
