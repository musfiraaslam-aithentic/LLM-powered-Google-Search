from selenium import webdriver
from selenium.webdriver.common.by import By
import time

# Start browser
driver = webdriver.Chrome()

# Open the target website
driver.get("https://www.viewsonic.com/us/viewsonic-warranty-lookup")

# Wait for the page to load
time.sleep(2)

try:
    # Decline cookies if the button is present
    element = driver.find_element(By.ID, "btn-cookie-decline")
    element.click()
    print("Clicked cookie decline button.")
    time.sleep(5)

    # Click on Step 2
    step2_button = driver.find_element(By.ID, "warranty-step-2")
    step2_button.click()
    print("Clicked warranty-step-2")
    time.sleep(5)

    # Now find the input field with ID 'warranty-s'
    serial_input = driver.find_element(By.ID, "warranty-s")
    serial_input.send_keys("V1X184402312")
    print("Typed serial number into warranty-s input field.")
    time.sleep(5)

        # Click on Step 2
    submit_button = driver.find_element(By.ID, "warranty-form-submit")
    time.sleep(5)
    submit_button.click()
    print("Clicked submit")
    time.sleep(2)

    

except Exception as e:
    print(f"Error occurred: {e}")

# Close the browser
driver.quit()
