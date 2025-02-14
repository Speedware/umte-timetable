from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from ics import Calendar, Event
from ics.alarm import DisplayAlarm
import pytz
import os
import tempfile
import caldav
from caldav.elements import dav
from concurrent.futures import ThreadPoolExecutor
from config import username, password, icloud_username, icloud_password

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")

user_data_dir = tempfile.mkdtemp()
options.add_argument(f"--user-data-dir={user_data_dir}")

login_url = "https://umeos.ru/login/index.php"
schedule_url = "https://umeos.ru/blocks/umerasp/schedule.php?t=student"

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def login():
    driver.get(login_url)
    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "username")))
    
    user_input = driver.find_element(By.ID, "username")
    pass_input = driver.find_element(By.ID, "password")
    login_button = driver.find_element(By.ID, "loginbtn")
    
    user_input.send_keys(username)
    pass_input.send_keys(password)
    login_button.click()
    WebDriverWait(driver, 5).until(EC.url_changes(login_url))

def parse_schedule():
    driver.get(schedule_url)
    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, "tabs__content")))

    html = driver.page_source

    soup = BeautifulSoup(html, "html.parser")
    schedule_data = []
    
    tabs = soup.find_all("div", class_="tabs__content")
    if not tabs:
        print("Вкладки расписания не найдены!")
        return []
    
    for tab in tabs:
        table = tab.find("table", class_="generaltable")
        if not table:
            continue
        
        rows = table.find_all("tr")
        if not rows:
            continue
        
        current_date = ""
        for row in rows:
            date_header = row.find("th", class_="cell c0 lastcol")
            if date_header:
                current_date = date_header.text.strip().split(" ")[-1]
                continue
            
            cols = row.find_all("td")
            if len(cols) < 4:
                continue
            
            number = cols[0].text.strip()
            time_range = cols[1].text.strip()
            start_time, end_time = time_range.split("-") if "-" in time_range else (time_range, "")
            room = cols[2].text.strip()
            
            subject_teacher_type = cols[3]
            subject = subject_teacher_type.find(text=True, recursive=False).strip()
            teacher = subject_teacher_type.find("br").next_sibling.strip() if subject_teacher_type.find("br") else ""


            type_spans = subject_teacher_type.find_all("span", class_="badge")
            types = [span.text.strip() for span in type_spans]
            
            if "вебинар" in types:
                type_ = "вебинар"
            else:
                type_ = types[0] if types else ""

            link = cols[3].find("a")["href"] if cols[3].find("a") else "-"
            
            schedule_data.append({
                "Date": current_date,
                "Number": number,
                "Start Time": start_time,
                "End Time": end_time,
                "Room": room,
                "Subject": subject,
                "Teacher": teacher,
                "Type": type_,
                "Link": link
            })
    
    return schedule_data

def create_ics(schedule, path="schedule.ics"):
    cal = Calendar()

    subject_replacements = {
        "Общая физическая подготовка": "Физкультура",
        "Основы противодействия экстремизму, терроризму и антикоррупционная политика Российской Федерации": "Противодействие ЭТ",
        "Информационные системы в экономике": "ИС в экономике",
        "Методика проведения исследовательских и опытно-конструкторских работ": "МПИиОКР",
        "Исследование операций и методы оптимизации (Теория игр и исследование операций)": "Теория игр",
        "Алгоритмизация и программирование": "Программирование"
    }

    timezone = pytz.timezone('Europe/Moscow')

    for lesson in schedule:
        event = Event()

        subject = lesson['Subject']
        short_subject = subject_replacements.get(subject, subject)

        if lesson['Type'] == "вебинар":
            event.name = f"{short_subject} (ДО)"
        else:
            event.name = f"{short_subject}"
        
        event.location = lesson['Room']

        description = f"Пара №{lesson['Number']}\nПреподаватель: {lesson['Teacher']}\nВид занятия: {lesson['Type']}"
        if lesson['Link'] != "-":
            description += f"\nСсылка: {lesson['Link']}"
        event.description = description
        
        date_str = lesson['Date']
        start_time_str = lesson['Start Time']
        end_time_str = lesson['End Time']
        
        start_datetime = timezone.localize(datetime.strptime(f"{date_str} {start_time_str}", "%d.%m.%Y %H:%M"))
        end_datetime = timezone.localize(datetime.strptime(f"{date_str} {end_time_str}", "%d.%m.%Y %H:%M"))
        
        event.begin = start_datetime
        event.end = end_datetime

        if lesson['Type'] == "вебинар":
            alarm = DisplayAlarm(trigger=timedelta(minutes=-30))
            event.alarms.append(alarm)

        cal.events.add(event)
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(cal.serialize())

def upload_to_icloud(ics_path):
    icloud_url = "https://caldav.icloud.com"
    calendar_name = "UMTE calDAV"

    client = caldav.DAVClient(url=icloud_url, username=icloud_username, password=icloud_password)
    principal = client.principal()

    try:
        calendar = principal.calendar(name=calendar_name)
    except caldav.lib.error.NotFoundError:
        print(f"Календарь '{calendar_name}' не найден. Создаем новый календарь...")
        calendar = principal.make_calendar(name=calendar_name)
        print(f"Календарь '{calendar_name}' успешно создан.")

    print("Очистка календаря от старых событий...")

    events = list(calendar.events())

    def delete_event(event):
        try:
            event.delete()
            print(f"Событие удалено: {event.instance.vevent.summary.value}")
        except Exception as e:
            print(f"Ошибка при удалении события: {e}")

    with ThreadPoolExecutor(max_workers=4) as executor:
        executor.map(delete_event, events)

    print("Календарь очищен.")

    with open(ics_path, "r", encoding="utf-8") as f:
        ics_data = f.read()

    from ics import Calendar as IcsCalendar
    ics_calendar = IcsCalendar(ics_data)

    def add_event(event):
        try:
            event_ics = event.serialize()
            calendar.add_event(event_ics)
            print(f"Событие '{event.name}' успешно добавлено.")
        except Exception as e:
            print(f"Ошибка при добавлении события '{event.name}': {e}")

    with ThreadPoolExecutor(max_workers=4) as executor:
        executor.map(add_event, ics_calendar.events)

login()
schedule = parse_schedule()

if not schedule:
    print("Расписание не найдено или данные отсутствуют!")
else:
    for lesson in schedule:
        print(f"Date: {lesson['Date']}")
        print(f"Number: {lesson['Number']}")
        print(f"Start Time: {lesson['Start Time']}")
        print(f"End Time: {lesson['End Time']}")
        print(f"Room: {lesson['Room']}")
        print(f"Subject: {lesson['Subject']}")
        print(f"Teacher: {lesson['Teacher']}")
        print(f"Type: {lesson['Type']}")
        print(f"Link: {lesson['Link']}")
        print("-" * 30)

    create_ics(schedule)
    upload_to_icloud("schedule.ics")

driver.quit()