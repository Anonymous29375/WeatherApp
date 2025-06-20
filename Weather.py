import FreeSimpleGUI as sg
import requests
from datetime import datetime, timezone
import pytz
import os

sg.theme("DarkGreen6")

# API Information
API_KEY = "db5620faef0a378e1f0a1ac502088363"
GEO_BASE_URL = "https://api.openweathermap.org/geo/1.0/direct"
WEATHER_BASE_URL = "https://api.openweathermap.org/data/3.0/onecall"

# Global setting for temperature unit
use_celsius = True

# Converts the temperature from Celsius to Fahrenheit
def celsius_to_fahrenheit(celsius):
    return (celsius * 9 / 5) + 32

# Converts a unix epoch to local time using time zone name (string)
def unix_to_local_time_zone(unix_time, timezone_str):
    utc_time = datetime.fromtimestamp(unix_time, tz=timezone.utc)
    local_tz = pytz.timezone(timezone_str)
    return utc_time.astimezone(local_tz)

# Get the latitude and longitude of a city
def get_city_coordinates(city):
    geo_url = f"{GEO_BASE_URL}?q={city}&limit=1&appid={API_KEY}"
    response = requests.get(geo_url)
    data = response.json()

    if response.status_code == 200 and not data:
        # The city name was not found
        return None, None, f"Is '{city}' a valid city?", response.status_code

    if response.status_code != 200 or not data:
        if data != None:
            msg = data.get("message", "City not found or API error.")
        else:
            msg = f"Unknown error occurred"

        return None, None, msg, response.status_code

    # Extract the Latitude and Longitude
    lat = data[0]["lat"]
    lon = data[0]["lon"]
    return lat, lon, None, response.status_code

# Get an icon using the icon label
def get_weather_icon(description):
    # Convert to lower case for easier comparison
    description = description.lower()

    # Matching label to icon name
    if "rain" in description:
        return "Icons/Rain.png"
    elif "scattered cloud" in description:
        return "Icons/PartlyCloudy.png"
    elif "overcast cloud" in description:
        return "Icons/Cloudy.png"
    elif "sunny" in description or "clear" in description:
        return "Icons/Sun.png"
    else:
        return "Icons/Cloudy.png"

# Get the 7-day weather forecast
def fetch_7_day_forecast(lat, lon, city):
    forecast_url = f"{WEATHER_BASE_URL}?lat={lat}&lon={lon}&appid={API_KEY}&exclude=hourly,minutely,current,alerts&units=metric"
    response = requests.get(forecast_url)
    data = response.json()

    if "daily" not in data:
        return (
            None,
            data.get("message", f"Unable to fetch forecast for city '{city}'"),
            response.status_code,
        )

    forecast_list = []

    # Iterate each daily data in 7 days
    for weather_day in data["daily"][:7]:
        # Format the date and convert the temps
        city_timestamp = weather_day["dt"]
        city_utc = datetime.fromtimestamp(city_timestamp, tz=timezone.utc)
        city_timezone_name = data.get("timezone", 0)
        city_timezone = pytz.timezone(city_timezone_name)

        city_local = city_utc.astimezone(city_timezone)
        date = city_local.strftime("%Y-%m-%d")
        temp_min_celsius = round(weather_day["temp"]["min"], 2)
        temp_max_celsius = round(weather_day["temp"]["max"], 2)
        temp_min_fahrenheit = round(celsius_to_fahrenheit(temp_min_celsius), 2)
        temp_max_fahrenheit = round(celsius_to_fahrenheit(temp_max_celsius), 2)

        # Extract the weather data
        description = weather_day["weather"][0]["description"]
        rain = weather_day.get("rain", 0)
        wind = weather_day["wind_speed"]
        humidity = weather_day["humidity"]
        sunrise_unix = weather_day["sunrise"]
        sunset_unix = weather_day["sunset"]

        # Convert sunrise and sunset to UTC
        sunrise_utc = datetime.fromtimestamp(sunrise_unix, tz=timezone.utc)
        sunset_utc = datetime.fromtimestamp(sunset_unix, tz=timezone.utc)

        # Convert to city local time
        city_timezone = pytz.timezone(city_timezone_name)
        sunrise_local = sunrise_utc.astimezone(city_timezone)
        sunset_local = sunset_utc.astimezone(city_timezone)

        # Converts the sunrise and sunset to Canberra time
        canberra_timezone = "Australia/Sydney"  # Canberra uses Sydney timezone
        sunrise_canberra = unix_to_local_time_zone(sunrise_unix, canberra_timezone)
        sunset_canberra = unix_to_local_time_zone(sunset_unix, canberra_timezone)

        # Adds weather details to the forecast list
        forecast_list.append(
            {
                "date": date,
                "temp_min_celsius": temp_min_celsius,
                "temp_max_celsius": temp_max_celsius,
                "temp_min_fahrenheit": temp_min_fahrenheit,
                "temp_max_fahrenheit": temp_max_fahrenheit,
                "description": description,
                "rain": rain,
                "wind": wind,
                "humidity": humidity,
                "sunrise_local": sunrise_local.strftime("%H:%M"),
                "sunset_local": sunset_local.strftime("%H:%M"),
                "sunrise_canberra": sunrise_canberra.strftime("%H:%M"),
                "sunset_canberra": sunset_canberra.strftime("%H:%M"),
            }
        )

    return forecast_list, None, response.status_code

def show_forecast_window(city, forecast_data):
    day_buttons = []
    for index, day in enumerate(forecast_data):
        day_of_week = datetime.strptime(day["date"], "%Y-%m-%d").strftime("%A")
        day_buttons.append(sg.Button(day_of_week, key=f"DAY_{index}", size=(12, 1)))

    layout = [
        [
            sg.Text(
                f"7-Day Forecast for {city}",
                font=("Helvetica", 14, "bold"),
                justification="center",
                expand_x=True,
            )
        ],
        [
            sg.Column(
                [[btn for btn in day_buttons]],
                justification="center",
            )
        ],
        [
            sg.Column(
                [[sg.Image(key="WEATHER_ICON")]],
                justification="center",
            )
        ],
        [
            sg.Column(
                [[sg.Multiline(size=(80, 12), key="FORECAST_OUTPUT", disabled=True)]],
                justification="center",
                element_justification="center",
            )
        ],
        [
            sg.Button("Close", size=(10, 1))
        ],
    ]

    window = sg.Window(
        f"Forecast - {city}",
        layout,
        modal=True,
        finalize=True,
    )

    while True:
        event, _ = window.read()
        if event in (sg.WIN_CLOSED, "Close"):
            break

        if event.startswith("DAY_"):
            index = int(event.split("_")[1])
            data = forecast_data[index]

            # Get appropriate icon path
            icon_path = get_weather_icon(data["description"])
            if not os.path.exists(icon_path):
                icon_path = "Icons/Cloudy.png"

            if use_celsius:
                min_temp = f"{data['temp_min_celsius']}°C"
                max_temp = f"{data['temp_max_celsius']}°C"
            else:
                min_temp = f"{data['temp_min_fahrenheit']}°F"
                max_temp = f"{data['temp_max_fahrenheit']}°F"

            forecast_text = (
                f"📅 {data['date']} ({datetime.strptime(data['date'], '%Y-%m-%d').strftime('%A')})\n"
                f"🌤 Description: {data['description'].capitalize()}\n"
                f"🌡 Min Temp: {min_temp}\n"
                f"🌡 Max Temp: {max_temp}\n"
                f"💧 Humidity: {data['humidity']}%\n"
                f"🌧 Rain: {data['rain']} mm\n"
                f"💨 Wind: {data['wind']} m/s\n"
                f"🌅 Sunrise ({city}): {data['sunrise_local']} | Sunset ({city}): {data['sunset_local']}\n"
                f"🇦🇺 Sunrise (Canberra): {data['sunrise_canberra']} | Sunset (Canberra): {data['sunset_canberra']}\n"
            )

            window["FORECAST_OUTPUT"].update(forecast_text)
            window["WEATHER_ICON"].update(filename=icon_path)

    window.close()

def show_settings_window():
    global use_celsius
    layout = [
        [sg.Text("Choose temperature unit:")],
        [sg.Radio("Celsius", "UNIT", key="C", default=use_celsius)],
        [sg.Radio("Fahrenheit", "UNIT", key="F", default=not use_celsius)],
        [sg.Button("Save"), sg.Button("Cancel")]
    ]
    window = sg.Window("Settings", layout, modal=True)
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, "Cancel"):
            break
        if event == "Save":
            use_celsius = values["C"]
            break
    window.close()

layout = [
    [sg.Text("City:")],
    [sg.InputText(key="CITY")],
    [sg.Button("Get Forecast"), sg.Button("Settings"), sg.Button("Exit")]
]

window = sg.Window("Weather Forecast App", layout)

while True:
    event, values = window.read()
    if event in (sg.WIN_CLOSED, "Exit"):
        break

    if event == "Settings":
        show_settings_window()

    if event == "Get Forecast":
        city = values["CITY"].strip()
        if not city:
            sg.popup_error("Please enter a city name.")
            continue

        lat, lon, error, response_code = get_city_coordinates(city)
        if error:
            sg.popup_error(
                f"Error fetching the city '{city}' coordinates: {error} [{response_code}]"
            )
            continue

        forecast, error, response_code = fetch_7_day_forecast(lat, lon, city)
        if error:
            sg.popup_error(
                f"Error fetching '{city}' forecast: {error} [{response_code}]"
            )
            continue

        show_forecast_window(city, forecast)

window.close()
