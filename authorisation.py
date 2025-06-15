import os
import json
import psycopg2
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

DB_CONFIG = {
    "user": "postgres",
    "password": "09112009",
    "host": "127.0.0.1",
    "port": "5433",
    "dbname": "wbauto"
}



def get_user_phone(user_id):
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT phone FROM wb WHERE id = %s", (user_id,))
                result = cur.fetchone()
                return result[0] if result else None
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return None



def load_user_data(phone):
    user_folder = f'data/user_{phone}'
    cookies_file = os.path.join(user_folder, 'cookies.json')
    storage_file = os.path.join(user_folder, 'storage.json')

    if not os.path.exists(cookies_file) or not os.path.exists(storage_file):
        print(f"❌ Данные для {phone} не найдены.")
        return None, None

    with open(cookies_file, 'r', encoding='utf-8') as f:
        cookies = json.load(f)

    with open(storage_file, 'r', encoding='utf-8') as f:
        storage = json.load(f)

    return cookies, storage



def login_wildberries(user_id):
    phone = get_user_phone(user_id)
    if not phone:
        print(f"❌ Пользователь с ID {user_id} не найден.")
        return None

    cookies, storage = load_user_data(phone)
    if not cookies or not storage:
        return None


    options = Options()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--no-sandbox')
    options.add_argument("start-maximized")

    driver = webdriver.Chrome(options=options)
    driver.get("https://www.wildberries.ru/lk")


    for cookie in cookies:
        driver.add_cookie(cookie)


    driver.execute_script(f"localStorage.setItem('wbx__tokenData', '{storage.get('wbx__tokenData', '')}')")
    driver.execute_script(f"localStorage.setItem('wbx_refresh', '{storage.get('wbx_refresh', '')}')")
    driver.execute_script(f"localStorage.setItem('wbx__sessionId', '{storage.get('wbx__sessionId', '')}')")


    driver.refresh()
    time.sleep(5)

    print(f"✅ Пользователь {phone} успешно авторизован на Wildberries!")
    return driver, phone



def save_user_data(driver, phone):
    user_folder = f'data/user_{phone}'
    os.makedirs(user_folder, exist_ok=True)


    cookies = driver.get_cookies()
    with open(os.path.join(user_folder, 'cookies.json'), 'w', encoding='utf-8') as f:
        json.dump(cookies, f, indent=4)


    storage = driver.execute_script("return {...localStorage};")
    with open(os.path.join(user_folder, 'storage.json'), 'w', encoding='utf-8') as f:
        json.dump(storage, f, indent=4)

    print(f"✅ Обновлённые данные сохранены для {phone}")



def process_users(user_ids):
    for user_id in user_ids:
        driver, phone = login_wildberries(user_id)
        if driver is None:
            continue

        print(f"💼 Работайте с аккаунтом {phone}. Введите 'done', когда завершите работу.")

        while True:
            command = input("Введите команду: ").strip().lower()
            if command == "done":
                break


        save_user_data(driver, phone)


        driver.quit()


user_ids = input("Введите ID пользователей через запятую: ").split(",")
user_ids = [id.strip() for id in user_ids if id.strip()]

process_users(user_ids)
