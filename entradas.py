from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
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
WAIT_TIMEOUT = 15  # Aumentado el timeout de espera

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
    return webdriver.Chrome(options=options)

def wait_and_click_element(driver, wait, element_id=None, css_selector=None, xpath=None):
    """
    Espera a que el elemento sea clickeable y lo hace click
    Retorna True si fue exitoso, False si falló
    """
    try:
        if element_id:
            element = wait.until(EC.element_to_be_clickable((By.ID, element_id)))
        elif css_selector:
            element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector)))
        elif xpath:
            element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        else:
            return False
        
        element.click()
        return True
    except TimeoutException:
        print(f"Timeout: No se pudo encontrar/clickear el elemento")
        return False
    except Exception as e:
        print(f"Error al clickear elemento: {e}")
        return False

def check_tickets():
    """
    Función principal que verifica las entradas
    Retorna True si el proceso fue exitoso, False si necesita reinicio
    """
    driver = None
    try:
        ahora = datetime.datetime.now(pytz.timezone('America/Buenos_Aires'))
        timestamp = ahora.strftime("%d/%m/%Y - %H:%M:%S")

        driver = setup_driver()
        wait = WebDriverWait(driver, WAIT_TIMEOUT)
        
        print(f"[{timestamp}] Iniciando proceso...")

        # Cargar la página principal
        driver.get("https://www.allaccess.com.ar/event/oasis")
        time.sleep(3)

        # Paso 1: Click en elemento con ID "75385"
        print("Paso 1: Buscando elemento 75385...")
        if not wait_and_click_element(driver, wait, element_id="75385"):
            print("Error en Paso 1: No se encontró el elemento 75385")
            return False
        time.sleep(2)

        # Paso 2: Click en botón "buyButton"
        print("Paso 2: Buscando buyButton...")
        if not wait_and_click_element(driver, wait, element_id="buyButton"):
            print("Error en Paso 2: No se encontró buyButton")
            return False
        time.sleep(3)

        # Paso 3: Click en elemento con data-value="218092"
        print("Paso 3: Buscando elemento data-value='218092'...")
        if not wait_and_click_element(driver, wait, css_selector='[data-value="218092"]'):
            print("Error en Paso 3: No se encontró el elemento data-value='218092'")
            return False
        time.sleep(2)

        # Paso 4: Click en elemento con data-value="104358"
        print("Paso 4: Buscando elemento data-value='104358'...")
        if not wait_and_click_element(driver, wait, css_selector='[data-value="104358"]'):
            print("Error en Paso 4: No se encontró el elemento data-value='104358'")
            return False
        time.sleep(4)

        # Paso 5: Extraer información de tarifas
        print("Paso 5: Extrayendo información de tarifas...")
        try:
            # Esperar a que aparezca el contenido
            wait.until(EC.presence_of_element_located((By.ID, "pickerContent")))
            time.sleep(2)  # Espera adicional para asegurar que el contenido se cargue
            
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
                wait_time = min(5 * retry_count, 15)  # Espera progresiva: 5s, 10s, 15s
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