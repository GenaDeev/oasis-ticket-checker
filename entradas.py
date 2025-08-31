from selenium import webdriver
from selenium.webdriver.chrome.options import Options
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

def normalize(text: str) -> str:
    text = text.lower().strip()
    text = "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )
    return " ".join(text.split())

options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument(f"--user-data-dir={tempfile.mkdtemp()}")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(options=options)
print("Iniciando proceso")

try:
    ahora = datetime.datetime.now(pytz.timezone('America/Buenos_Aires'))
    timestamp = ahora.strftime("%d/%m/%Y - %H:%M:%S")

    driver.get("https://www.allaccess.com.ar/event/oasis")
    time.sleep(2)

    driver.execute_script('document.getElementById("75385").click()')
    time.sleep(1)

    driver.execute_script('document.getElementById("buyButton").click()')
    time.sleep(2)

    driver.execute_script('document.querySelector(\'[data-value="218092"]\').click()')
    time.sleep(1)

    driver.execute_script('document.querySelector(\'[data-value="104358"]\').click()')
    time.sleep(3)

    tarifas_js = driver.execute_script("""
        const list = document.getElementById("pickerContent");
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

finally:
    driver.quit()
