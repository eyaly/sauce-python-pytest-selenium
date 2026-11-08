from selenium.webdriver.common.by import By

BASE_URL = "https://www.saucedemo.com"


def login(driver, username, password="secret_sauce"):
    driver.get(BASE_URL)
    driver.find_element(By.ID, "user-name").send_keys(username)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.ID, "login-button").click()


def test_valid_login(driver):
    login(driver, "standard_user")

    assert "/inventory.html" in driver.current_url
    assert driver.find_element(By.CLASS_NAME, "title").text == "Products"


def test_locked_out_user(driver):
    login(driver, "locked_out_user")

    error = driver.find_element(By.CSS_SELECTOR, "[data-test='error']")
    assert "Sorry, this user has been locked out." in error.text


def test_missing_username(driver):
    login(driver, "")

    error = driver.find_element(By.CSS_SELECTOR, "[data-test='error']")
    assert "Hi you - Username is required" in error.text
