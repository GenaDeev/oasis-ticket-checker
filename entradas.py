from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException
from dotenv import load_dotenv
import time
import unicodedata
from pushbullet import Pushbullet
import datetime
import os
import tempfile
import pytz
import shutil

load_dotenv()
PB_API_KEY = os.getenv("PB_API_KEY") or ""
pb = None
if PB_API_KEY:
    pb = Pushbullet(PB_API_KEY)

HEADLESS = os.getenv("IS_HEADLESS", "true").lower() == "true"

targetTarifaName = os.getenv("TARGET_TARIFA_NAME") or "campo general 1"
MAX_RETRIES = 3
WAIT_TIMEOUT = 15


def log(msg):
    ahora = datetime.datetime.now(pytz.timezone("America/Buenos_Aires"))
    timestamp = ahora.strftime("%d/%m/%Y - %H:%M:%S")
    print(f"[{timestamp}] {msg}")


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )
    return " ".join(text.split())


CHROME_USER_DATA_DIR = os.path.join(os.getcwd(), "chrome_data")
os.makedirs(CHROME_USER_DATA_DIR, exist_ok=True)


def cleanup_chrome_cache():
    cache_dir = os.path.join(CHROME_USER_DATA_DIR, "Default", "Cache")
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            os.makedirs(cache_dir)
        except Exception as e:
            log(f"⚠️ No se pudo limpiar cache: {e}")


def setup_driver():
    cleanup_chrome_cache()
    options = Options()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_experimental_option("useAutomationExtension", False)
    service = Service(log_path=os.devnull)
    return webdriver.Chrome(options=options, service=service)


def click_via_js(driver, element):
    driver.execute_script("arguments[0].click();", element)


def wait_and_click_element(
    driver, wait, element_id=None, css_selector=None, xpath=None
):
    try:
        if element_id:
            element = wait.until(EC.presence_of_element_located((By.ID, element_id)))
        elif css_selector:
            element = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
            )
        elif xpath:
            element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        else:
            return False
        click_via_js(driver, element)
        return True
    except TimeoutException:
        log(f"⚠️ Timeout: No se pudo encontrar/clickear el elemento")
        return False
    except Exception as e:
        log(f"❌ Error al clickear elemento: {e}")
        return False


def check_tickets():
    driver = None
    try:
        driver = setup_driver()
        wait = WebDriverWait(driver, WAIT_TIMEOUT)
        log("ℹ️ Iniciando proceso de checkeo de tickets...")

        driver.get("https://www.allaccess.com.ar/event/oasis")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        pasos = [
            ("75385", "id"),
            ("buyButton", "id"),
            ('[data-value="218092"]', "css"),
            ('[data-value="104358"]', "css"),
        ]

        for idx, (selector, tipo) in enumerate(pasos, 1):
            if tipo == "id":
                success = wait_and_click_element(driver, wait, element_id=selector)
            elif tipo == "css":
                success = wait_and_click_element(driver, wait, css_selector=selector)
            if not success:
                log(f"❌ Paso {idx}: no se pudo clickear el elemento ({selector})")
                return False
            log(f"✅ Paso {idx}: elemento clickeado ({selector})")
            time.sleep(1)

        log("ℹ️ Extrayendo información de tarifas...")
        try:
            wait.until(EC.presence_of_element_located((By.ID, "pickerContent")))
            time.sleep(1)
            tarifas_js = driver.execute_script(
                """
                const list = document.getElementById("pickerContent")?.children[0];
                const modal = document.querySelector('.modal_new');
                if (modal) modal.remove();
                if (!list) return null;
                let result = [];
                for (const tarifa of list.children){
                    try {
                        const soldOut = !tarifa.hasAttribute('data-value');
                        let nombre;
                        if (soldOut) {
                            nombre = tarifa.children[2]?.children[0]?.textContent || '';
                        } else {
                            nombre = tarifa.children[1]?.children[0]?.textContent || '';
                        }
                        result.push({nombre, soldOut});
                    } catch(e){}
                }
                return result;
            """
            )
            if not tarifas_js:
                log("❌ No se pudo extraer información de tarifas")
                return False
        except TimeoutException:
            log("❌ No se encontró pickerContent")
            return False

        found = False
        agotado = False
        normalizedTarget = normalize(targetTarifaName)

        for t in tarifas_js:
            nombre = t["nombre"].strip()
            soldOut = t["soldOut"]
            estado = "AGOTADO ❌" if soldOut else "DISPONIBLE ✅"
            log(f"   • {nombre}: {estado}")

            if normalizedTarget in normalize(nombre):
                found = True
                if soldOut:
                    agotado = True
                break

        if found and not agotado:
            if PB_API_KEY:
                pb.push_link(
                    title="✅🎫 HAY ENTRADAS YA! ENTRA AHORA.",
                    url="https://www.allaccess.com.ar/event/oasis",
                )
            log(
                f"✅ Hay entradas disponibles en {targetTarifaName}. Notificado por Pushbullet."
            )
        elif found and agotado:
            if PB_API_KEY:
                pb.push_link(
                    title="❕️🎫 OJO, APARECIO LA OPCION ELEGIDA PERO SIN STOCK AUN.",
                    url="https://www.allaccess.com.ar/event/oasis",
                )
            log(f"⚠️ {targetTarifaName} aparece en la lista, pero está agotado")
        else:
            log(f"ℹ️ {targetTarifaName} no aparece en la lista")

        return True
    except Exception as e:
        log(f"❌ Error inesperado: {e}")
        return False
    finally:
        if driver:
            driver.quit()


# --- INICIO DEL SCRIPT ---
start_time = time.time()
log("==================== INICIO DE PROCESO ====================")
log("ℹ️ Iniciando proceso con reintentos automáticos...")

retry_count = 0
while retry_count < MAX_RETRIES:
    try:
        success = check_tickets()
        if success:
            log("✅ Proceso completado exitosamente.")
            break
        else:
            retry_count += 1
            if retry_count < MAX_RETRIES:
                wait_time = min(5 * retry_count, 15)
                log(
                    f"⚠️ Reintento {retry_count}/{MAX_RETRIES} en {wait_time} segundos..."
                )
                time.sleep(wait_time)
            else:
                log("❌ Se agotaron todos los reintentos. El proceso falló.")
    except KeyboardInterrupt:
        log("⚠️ Proceso interrumpido por el usuario.")
        break
    except Exception as e:
        log(f"❌ Error crítico: {e}")
        retry_count += 1
        if retry_count < MAX_RETRIES:
            log(f"⚠️ Reintentando... ({retry_count}/{MAX_RETRIES})")
            time.sleep(5)

end_time = time.time()
duration = end_time - start_time
log(f"🕒 Duración total de esta iteración: {duration:.2f} segundos")
log("==================== FIN DE PROCESO ====================")
