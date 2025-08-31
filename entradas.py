from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import unicodedata
from pushbullet import Pushbullet
import datetime
import os

PB_API_KEY = os.environ.get("PB_API_KEY")
pb = Pushbullet(PB_API_KEY)

targetTarifaName = "oasis collectors package"

def normalize(text: str) -> str:
    text = text.lower().strip()
    text = "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )
    return " ".join(text.split())

options = Options()
driver = webdriver.Chrome(options=options)
print("Iniciando proceso")

try:
    # ts
    ahora = datetime.datetime.utcnow() - datetime.timedelta(hours=3)
    timestamp = ahora.strftime("%d%m%Y - %H:%M:%S")

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
        push = pb.push_link(
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
