from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import unicodedata
from pushbullet import Pushbullet
import datetime
import os
import tempfile
import pytz

PB_API_KEY = os.environ.get("PB_API_KEY")
pb = Pushbullet(PB_API_KEY)

targetTarifaName = "campo general 1"
MAX_RETRIES = 3
WAIT_TIMEOUT = 15

def normalize(text: str) -> str:
    text = text.lower().strip()
    text = "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )
    return " ".join(text.split())

def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-data-dir={tempfile.mkdtemp()}")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return webdriver.Chrome(options=options)

def click_via_js(driver, element):
    driver.execute_script("arguments[0].click();", element)

def wait_and_click_element(driver, wait, element_id=None, css_selector=None, xpath=None):
    try:
        if element_id:
            element = wait.until(EC.presence_of_element_located((By.ID, element_id)))
        elif css_selector:
            element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, css_selector)))
        elif xpath:
            element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        else:
            return False
        
        click_via_js(driver, element)
        return True
    except TimeoutException:
        print(f"Timeout: No se pudo encontrar/clickear el elemento")
        return False
    except Exception as e:
        print(f"Error al clickear elemento: {e}")
        return False

def check_tickets():
    driver = None
    try:
        ahora = datetime.datetime.now(pytz.timezone('America/Buenos_Aires'))
        timestamp = ahora.strftime("%d/%m/%Y - %H:%M:%S")

        driver = setup_driver()
        wait = WebDriverWait(driver, WAIT_TIMEOUT)
        
        print(f"[{timestamp}] Iniciando proceso...")

        driver.get("https://www.allaccess.com.ar/event/oasis")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Paso 1
        print("Paso 1: Buscando elemento 75385...")
        if not wait_and_click_element(driver, wait, element_id="75385"):
            print("Error en Paso 1")
            return False
        time.sleep(1)

        # Paso 2
        print("Paso 2: Buscando buyButton...")
        if not wait_and_click_element(driver, wait, element_id="buyButton"):
            print("Error en Paso 2")
            return False
        time.sleep(1)

        # Paso 3
        print("Paso 3: Buscando elemento data-value='218092'...")
        if not wait_and_click_element(driver, wait, css_selector='[data-value="218092"]'):
            print("Error en Paso 3")
            return False
        time.sleep(1)

        # Paso 4
        print("Paso 4: Buscando elemento data-value='104358'...")
        if not wait_and_click_element(driver, wait, css_selector='[data-value="104358"]'):
            print("Error en Paso 4")
            return False
        time.sleep(1)

        # Paso 5: Extracción de tarifas (igual que tu original)
        print("Paso 5: Extrayendo información de tarifas...")
        try:
            wait.until(EC.presence_of_element_located((By.ID, "pickerContent")))
            time.sleep(1)
            
            tarifas_js = driver.execute_script("""
                const list = document.getElementById("pickerContent");
                if (!list) return null;
                let result = [];
                for (const tarifa of list.children){
                    try {
                        const nombre = tarifa.children[0].children[2].children[0].textContent;
                        const soldOut = tarifa.children[0].children[0].textContent;
                        result.push({nombre, soldOut});
                    } catch(e){}
                }
                return result;
            """)

            if tarifas_js is None or len(tarifas_js) == 0:
                print("Error en Paso 5: No se pudo extraer información de tarifas")
                return False

        except TimeoutException:
            print("Error en Paso 5: No se encontró pickerContent")
            return False

        # Procesar resultados
        found = False
        agotado = False
        normalizedTarget = normalize(targetTarifaName)

        for t in tarifas_js:
            nombre = normalize(t['nombre'])
            soldOut = t['soldOut'].strip().lower()

            if nombre == normalizedTarget:
                found = True
                if "agotado" in soldOut:
                    agotado = True
                break

        if found and not agotado:
            pb.push_link(
                title="✅🎫 HAY ENTRADAS YA! ENTRA AHORA.",
                url="https://www.allaccess.com.ar/event/oasis"
            )
            print(f"[{timestamp}] Hay entradas disponibles en {targetTarifaName}. Notificado por Pushbullet.")
        elif found and agotado:
            print(f"[{timestamp}] {targetTarifaName} aparece en la lista, pero está agotado")
        else:
            print(f"[{timestamp}] {targetTarifaName} ni siquiera aparece en la lista")

        return True

    except Exception as e:
        print(f"Error inesperado: {e}")
        return False
    finally:
        if driver:
            driver.quit()

# Proceso principal con reintentos
print("Iniciando proceso con reintentos automáticos...")
retry_count = 0

while retry_count < MAX_RETRIES:
    try:
        success = check_tickets()
        
        if success:
            print("Proceso completado exitosamente.")
            break
        else:
            retry_count += 1
            if retry_count < MAX_RETRIES:
                wait_time = min(5 * retry_count, 15)
                print(f"Reintento {retry_count}/{MAX_RETRIES} en {wait_time} segundos...")
                time.sleep(wait_time)
            else:
                print("Se agotaron todos los reintentos. El proceso falló.")
                
    except KeyboardInterrupt:
        print("Proceso interrumpido por el usuario.")
        break
    except Exception as e:
        print(f"Error crítico: {e}")
        retry_count += 1
        if retry_count < MAX_RETRIES:
            print(f"Reintentando... ({retry_count}/{MAX_RETRIES})")
            time.sleep(5)

print("Finalizando script.")