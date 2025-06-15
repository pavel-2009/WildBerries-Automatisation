import time
import random
import json
import uuid
import requests
import psycopg2
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os

API_KEY = "3a6a8d73a9d74caba8c1b7836e01f039"
SMS_SERVICE = "wb"
REGISTRATION_URL = "https://www.wildberries.ru/"
TELEGRAM_TOKEN = ""
TELEGRAM_CHAT_ID = ""

DB_CONFIG = {
    "user": "postgres",
    "password": "09112009",
    "host": "127.0.0.1",
    "port": "5433",
    "dbname": "wbauto"
}

# Проверка подключения к БД
try:
    conn = psycopg2.connect(**DB_CONFIG)
    conn.close()
except Exception as e:
    print(f"❌ Ошибка подключения к базе данных: {e}")
    exit(1)


def send_telegram(message):
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
        print(f"❌ Ошибка получения номера: {e}")
        return None, None


def get_sms(driver, number_id):
    for attempt in range(30):
        time.sleep(2)


        try:
            driver.find_element(By.CLASS_NAME, 'j-error-full-phone')
            print(f"⚠️ Ошибка: номер уже используется.")
            break
        except:
            pass


        try:
            resp = requests.get(
                f"https://vak-sms.com/api/getSmsCode/?apiKey={API_KEY}&idNum={number_id}", timeout=10
            )
            resp.raise_for_status()
            data = resp.json()

            return data["smsCode"]
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка запроса SMS-кода: {e}")
        except json.JSONDecodeError:
            print("❌ Ошибка обработки JSON-ответа.")

    print(f"⚠️ SMS-код не получен за 60 секунд для номера {number_id}")
    return None


def init_driver():
    try:
        options = Options()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--no-sandbox')
        return webdriver.Chrome(options=options)
    except Exception as e:
        print(f"❌ Ошибка инициализации драйвера: {e}")
        return None


def save_account_to_db(account):
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO wb (
                        id, wbx_token_data, wbx_refresh, wbx_session_id,
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
        print(f"❌ Ошибка сохранения аккаунта в БД: {e}")


def register_user(index):
    driver = init_driver()
    if not driver:
        return

    wait = WebDriverWait(driver, 20)
    try:
        driver.get(REGISTRATION_URL)
        time.sleep(3)
        wait.until(EC.element_to_be_clickable(
            (By.CLASS_NAME, 'navbar-pc__icon--profile'))).click()

        num_id, phone = get_number()
        if not num_id or not phone:
            print("❌ Не удалось получить номер, регистрация отменена.")
            return

        input_tel = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'input.input-item')))
        input_tel.clear()
        for i in str(phone):
            input_tel.send_keys(i)
            time.sleep(0.3)

        time.sleep(3)
        btn = driver.find_element(By.CLASS_NAME, "login__btn.btn-main-lg")
        btn.click()

        code = get_sms(driver, num_id)

        if not code:
            print(f"❌ Не удалось получить SMS-код для номера {phone}")
            try:
                wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//*[text()='Запросить код ещё раз']"))).click()
                time.sleep(3)
                code = get_sms(driver, num_id)
            except:
                print("⚠️ Кнопка 'Запросить код ещё раз' не найдена.")

        for i, el in zip(code, driver.find_elements(By.CLASS_NAME, "char-input__item")):
            el.send_keys(i)
            time.sleep(0.3)
            time.sleep(3)
            driver.get("https://www.wildberries.ru/lk")

            name = random.choice(('Иван', 'Петр', 'Мария', 'Александр'))
            sex = random.choice(['Мужской', 'Женский'])

            balance = 0
            try:
                balance = int(driver.find_element(
                    By.CLASS_NAME, 'lk-item__title--balance').text.replace('₽', '').strip())
            except:
                pass

            user_folder = f'data/user_{phone}'
            os.makedirs(user_folder, exist_ok=True)


            cookies = driver.get_cookies()
            with open(f'data/user_{phone}/cookies.json', 'w', encoding='utf-8') as f:
                json.dump(cookies, f, indent=4)

            storage = driver.execute_script("return {...localStorage};")
            with open(f'data/user_{phone}/storage.json', 'w', encoding='utf-8') as f:
                json.dump(storage, f, indent=4)

            account = {
                "id": str(uuid.uuid4())[:10],
                "wbx_token_data": json.loads(storage.get("wbx__tokenData", "{}")).get('token', ''),
                "wbx_refresh": requests.get("https://wbx-auth.wildberries.ru/v2/auth/slide-v3").cookies.get('wbx-refresh', ''),
                "wbx_session_id": storage.get("wbx__sessionID", ''),
                "datetime": datetime.now(),
                "status": True,
                "sex": sex,
                "name": name,
                "phone": "+" + phone,
                "balance": balance,
                "last_action": "registration"
            }

            save_account_to_db(account)
            print(f"✅ Аккаунт создан: {account['phone']}, баланс: {account['balance']}₽")

    finally:
        driver.quit()


def main():
    threads = int(input("Сколько потоков запустить: "))
    accounts = int(input("Сколько аккаунтов зарегистрировать: "))
    with ThreadPoolExecutor(max_workers=threads) as executor:
        executor.map(register_user, range(accounts))


if __name__ == '__main__':
    main()
