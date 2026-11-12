from selenium import webdriver
import chromedriver_autoinstaller
from time import sleep
import urllib.request
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

chromedriver_autoinstaller.install(no_ssl=True)

driver=webdriver.Chrome()

url="https://ttport.turktelekom.com.tr/"

driver.get(url)

driver.quit
