# UMTE Timetable

This project provides the ability to automatically collect data on the class schedule from the educational portal [umeos.ru](https://umeos.ru/login/index.php). of St. Petersburg University of Management Technologies and Economics. The resulting schedule is exported to a convenient .ics format, which allows you to easily integrate it into popular calendars such as Google Calendar, Apple Calendar and others, ensuring the convenience of planning and organizing the educational process.

#### Features
- Automatic login using the student's login and password.
- Notifications 30 minutes before the start of webinars.
- Saving the schedule when umeos.ru is unavailable

#### Setup
Create a configuration file `config.py` and change the values ​​of the variables `username` and `password` to your login credentials for the [umeos.ru](https://umeos.ru/login/index.php) website.
```python
username = "YOUR_USERNAME"
password = "YOUR_PASSWORD"
```

The project requires several Python libraries to be installed. All dependencies are listed in the `requirements.txt` file, go to your project directory and run the command:
```bash
pip install -r requirements.txt
```

The project uses Selenium to automate the Chrome browser. If you do not have ChromeDriver installed, it will be automatically installed using `webdriver-manager`. However, make sure you have Google Chrome installed.