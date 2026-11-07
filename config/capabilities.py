"""Sauce Labs desktop browser (VM) capabilities.

Each key is a browser name you can pass to `--browser`.
Edit / add entries here to change platforms or add browsers.
Platform configurator: https://saucelabs.com/products/platform-configurator
"""

CAPABILITIES = {
    "chrome": {
        "browserName": "chrome",
        "browserVersion": "latest",
        "platformName": "Windows 11",
    },
    "safari": {
        "browserName": "safari",
        "browserVersion": "latest",
        "platformName": "macOS 13",
    },
    "firefox": {
        "browserName": "firefox",
        "browserVersion": "latest",
        "platformName": "macOS 13",
    },
    "edge": {
        "browserName": "MicrosoftEdge",
        "browserVersion": "latest",
        "platformName": "Windows 11",
    },
}
