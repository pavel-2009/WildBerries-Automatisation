import time
import random
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import psycopg2
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
import uuid

API_KEY = "3a6a8d73a9d74caba8c1b7836e01f039"
SMS_SERVICE = "wb"
REGISTRATION_URL = "https://www.wildberries.ru/"
TELEGRAM_TOKEN = ""
TELEGRAM_CHAT_ID = ""

DB_CONFIG = {
    "user": "postgres",
    "password": "09112009",
    "host": "127.0.0.1",
    "port": "5432",
}

try:
    conn = psycopg2.connect(**DB_CONFIG)
    conn.close()
except Exception as e:
    print(f"❌ Ошибка подключения к базе данных: {e}")
    exit(1)

def check_existing_account(phone):
    try:
        with psycopg2.connect(dbname='wildberries', password='09112009', host='localhost', port='5432') as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM accounts WHERE phone = %s", (phone,))
                account = cur.fetchone()
                if account:
                    return "reuse" if not account[5] else "used"
                return "new"
    except Exception as e:
        send_telegram_log(f"❌ Ошибка проверки аккаунта: {e}")
        return "error"

def send_telegram_log(message):
    try:
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                     params={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print("❌ Ошибка отправки лога в Telegram:", e)

def get_number():
    time.sleep(random.uniform(1, 3))
    url = f"https://vak-sms.com/api/getNumber/?apiKey={API_KEY}&service={SMS_SERVICE}&country=ru"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "idNum" not in data or "tel" not in data:
            raise ValueError(f"❌ Ошибка получения номера: {data}")

        return data["idNum"], data["tel"]
    except Exception as e:
        send_telegram_log(f"❌ Ошибка получения номера: {e}")
        return None, None

def get_sms(number_id):
    for _ in range(30):
        time.sleep(2)
        try:
            resp = requests.get(
                f"https://vak-sms.com/api/getSmsCode/?apiKey={API_KEY}&idNum={number_id}", timeout=10
            ).json()
            if resp.get('smsCode'):
                return resp["smsCode"]
        except Exception as e:
            send_telegram_log(f"❌ Ошибка получения SMS-кода: {e}")
    send_telegram_log(f"⚠️ SMS-код не получен за 60 секунд для номера {number_id}")
    return None

def init_driver():
    try:
        options = Options()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--no-sandbox')
        return webdriver.Chrome(options=options)
    except Exception as e:
        send_telegram_log(f"❌ Ошибка инициализации драйвера: {e}")
        return None

def save_account_to_db(account):
    try:
        with psycopg2.connect(dbname='wildberries', password='09112009', host='localhost', port='5432') as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO accounts (
                        wbx_token_data, wbx_refresh, wbx_session_id,
                        datetime, status, sex, name, phone, balance, last_action
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    account['id'], account['wbx_token_data'], account['wbx_refresh'], account['wbx_session_id'],
                    account['datetime'], account['status'], account['sex'], account['name'], account['phone'],
                    account['balance'], account['last_action']
                ))
                conn.commit()
    except Exception as e:
        print(f"❌ Ошибка сохранения аккаунта в БД: {e}")
        send_telegram_log(f"❌ Ошибка сохранения аккаунта в БД: {e}")

def register_user(index):
    driver = init_driver()
    if not driver:
        return

    wait = WebDriverWait(driver, 20)
    try:
        driver.get(REGISTRATION_URL)
        time.sleep(3)
        wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'navbar-pc__icon--profile'))).click()

        num_id, phone = get_number()
        if not num_id or not phone:
            send_telegram_log("❌ Не удалось получить номер, регистрация отменена.")
            return

        input_tel = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input.input-item')))
        input_tel.clear()
        for i in str(phone):
            input_tel.send_keys(i)
            time.sleep(0.3)

        wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='Получить код']"))).click()
        code = get_sms(num_id)
        if not code:
            send_telegram_log(f"❌ Не удалось получить SMS-код для номера {phone}")
            return

        for i, el in zip(code, driver.find_elements(By.CLASS_NAME, "char-input__item")):
            el.send_keys(i)
            time.sleep(0.3)

        time.sleep(3)

        driver.get("https://www.wildberries.ru/lk")

        try:
            wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='Имя не указано']"))).click()
            name = random.choice(('Иван', 'Петр', 'Мария', 'Александр'))
            name_input = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "form-block__input--MytTa")))
            for i in name:
                name_input.send_keys(i)
                time.sleep(0.4)

            sex = random.choice(['Мужской', 'Женский'])
            wait.until(EC.element_to_be_clickable((By.XPATH, f"//*[text()='{sex}']"))).click()
            wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='Сохранить']"))).click()
        except:
            name = driver.find_element(By.CLASS_NAME, "lk-item__title.lk-item__title--user-name").text
            sex = random.choice(['Мужской', 'Женский'])

        balance = driver.find_element(By.CLASS_NAME, 'lk-item__title--balance').text.replace('₽', '').strip()
        storage = driver.execute_script("return {...localStorage};")

        status = check_existing_account("+" + phone)
        last_action = "authorization" if status in ["used", "reuse"] else "registration"

        account = {
            "id": str(uuid.uuid4().int[:10]),
            "wbx_token_data": json.loads(storage["wbx__tokenData"])['token'],
            "wbx_refresh": requests.get("https://wbx-auth.wildberries.ru/v2/auth/slide-v3").cookies.get('wbx-refresh'),
            "wbx_session_id": storage["wbx__sessionID"],
            "datetime": datetime.now(),
            "status": True,
            "sex": sex,
            "name": name,
            "phone": "+" + phone,
            "balance": int(balance or 0),
            "last_action": last_action
        }

        save_account_to_db(account)
        send_telegram_log(f"✅ Аккаунт создан: {account['phone']}, баланс: {account['balance']}₽")

    except Exception as e:
        send_telegram_log(f"❌ Ошибка регистрации #{index}: {e}")
    finally:
        if driver:
            driver.quit()

def main():
    with ThreadPoolExecutor(max_workers=int(input("Сколько потоков запустить: "))) as executor:
        executor.map(register_user, range(int(input("Сколько аккаунтов зарегистрировать: "))))

if __name__ == '__main__':
    main()
