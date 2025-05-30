from django.test import LiveServerTestCase
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from django.contrib.auth.models import User

class InterfaceTest(LiveServerTestCase):
    def setUp(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Executa o Chrome em modo headless (sem interface gráfica)
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Criar um utilizador de teste
        self.user = User.objects.create_user(
            username='test_user',
            password='test_password',
            first_name='Test',
            last_name='User'
        )

    def tearDown(self):
        self.driver.quit()

    def test_login(self):
        self.driver.get(f"{self.live_server_url}/login/")
        username_input = self.driver.find_element(By.NAME, "username")
        password_input = self.driver.find_element(By.NAME, "password")
        username_input.send_keys("test_user")
        password_input.send_keys("test_password")
        password_input.send_keys(Keys.RETURN)
        
        # Esperar que a página de boas-vindas carregue
        wait = WebDriverWait(self.driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "alert-success")))
        
        self.assertIn("Bem-vindo", self.driver.page_source) 