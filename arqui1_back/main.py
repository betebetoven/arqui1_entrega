from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from gpiozero import LED, Servo
from RPLCD.i2c import CharLCD
import time
import uvicorn
import asyncio
import RPi.GPIO as GPIO
import pygame

# Define the FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize pygame mixer for alarm sound
pygame.mixer.init()
sound_file = "alarma2.mp3"
pygame.mixer.music.load(sound_file)

# Define the LEDs and their states
led_pins = [4, 17, 27, 22, 5, 6, 13, 14]
led_names = ["BAÑO", "CARGA-DESCARGA", "COMEDOR", "AREA-TRABAJO", "CONFERENCIA", "ADMINISTRACION", "RECEPCION", "EXTERIOR"]
leds = [LED(pin) for pin in led_pins]
led_states = [False] * len(leds)

# Initialize the I2C LCD
lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, cols=16, rows=2, dotsize=8)

# Initialize the light sensor and laser receiver
GPIO.setmode(GPIO.BCM)
GPIO.setup(16, GPIO.IN)  # Light sensor
GPIO.setup(12, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # Laser receiver
GPIO.setup(7, GPIO.OUT)  # Laser emitter

# Initialize the servo motor
servo = Servo(18)
servo.value = None
servo_state = False

# Initialize the snap-action switch pins
entry_pin = 20
exit_pin = 21
GPIO.setup(entry_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(exit_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Initialize people counter
people_count = 0
button_was_pressed_entry = False
button_was_pressed_exit = False

# GPIO pin mappings for each segment of the 7-segment display
segment_pins = {
    'a': 10,
    'b': 19,
    'c': 26,
    'd': 9,
    'e': 11,
    'f': 23,
    'g': 24
}

# Define the GPIO setup for the 7-segment display
for pin in segment_pins.values():
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

# Define the segments for each digit (0-9)
digits = {
    0: [True, True, True, True, True, True, False],
    1: [False, True, True, False, False, False, False],
    2: [True, True, False, True, True, False, True],
    3: [True, True, True, True, False, False, True],
    4: [False, True, True, False, False, True, True],
    5: [True, False, True, True, False, True, True],
    6: [True, False, True, True, True, True, True],
    7: [True, True, True, False, False, False, False],
    8: [True, True, True, True, True, True, True],
    9: [True, True, True, True, False, True, True],
}

# Function to display a digit on the 7-segment display
def display_digit(digit):
    segments = digits[digit]
    for segment, pin in segment_pins.items():
        GPIO.output(pin, segments[list(segment_pins.keys()).index(segment)])

# Function to play the alarm sound
def play_sound():
    if not pygame.mixer.music.get_busy():  # Check if no sound is currently playing
        pygame.mixer.music.play()
        print("Alarm triggered: Laser cut off, playing sound.")
        for ws in connected_websockets:
            asyncio.create_task(ws.send_json({"alarm": True}))

# Function to stop the alarm sound
def stop_sound():
    if pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()
        print("Alarm stopped.")
        for ws in connected_websockets:
            asyncio.create_task(ws.send_json({"alarm": False}))

# Initialize the RC motor
GPIO.setup(15, GPIO.OUT)
GPIO.output(15, GPIO.HIGH)  # Ensure the RC motor is off initially
rc_motor_state = False

connected_websockets = []

# Function to toggle an LED
def toggle_led(led_index):
    global led_states
    if 0 <= led_index < len(leds):
        led_states[led_index] = not led_states[led_index]
        if led_states[led_index]:
            leds[led_index].on()
        else:
            leds[led_index].off()
    # Special handling for the outside LED (GPIO 14)
    if led_index == len(led_pins) - 1:
        for ws in connected_websockets:
            asyncio.create_task(ws.send_json({"outside_led": led_states[led_index]}))

# Function to toggle the RC motor
def toggle_rc_motor():
    global rc_motor_state
    rc_motor_state = not rc_motor_state
    GPIO.output(15, GPIO.LOW if rc_motor_state else GPIO.HIGH)
    for ws in connected_websockets:
        asyncio.create_task(ws.send_json({"rc_motor_state": rc_motor_state}))

# Function to update the LCD with LED states
def update_lcd():
    lcd.clear()
    lcd.write_string("LED States:\n")
    for i, state in enumerate(led_states):
        lcd.clear()
        lcd.write_string(f"{led_names[i]}: {'On' if state else 'Off'} ")
        time.sleep(0.8)
        
def update_single_lcd(index: int):
    try:
        lcd.clear()
        lcd.write_string(f"{led_names[index]}: {'On' if led_states[index] else 'Off'} ")
    except Exception as e:
        print(e)



# Function to toggle the servo motor
def toggle_servo():
    global servo_state
    servo.value = 1
    servo_state = not servo_state
    if servo_state:
        servo.max()
    else:
        servo.min()
    time.sleep(0.15)
    servo.value = None

# Function to update people count
def update_people_count(change):
    global people_count
    people_count += change
    people_count = max(0, people_count)  # Ensure people_count is not negative
    display_digit(people_count % 10)  # Display only the last digit for simplicity
    for ws in connected_websockets:
        asyncio.create_task(ws.send_json({"people_count": people_count}))

# Background task to monitor the entry pin
async def monitor_entry_pin():
    global button_was_pressed_entry
    while True:
        input_state = GPIO.input(entry_pin)
        if input_state == GPIO.LOW:
            if not button_was_pressed_entry:
                update_people_count(1)
                button_was_pressed_entry = True
        else:
            button_was_pressed_entry = False
        await asyncio.sleep(0.05)

# Background task to monitor the exit pin
async def monitor_exit_pin():
    global button_was_pressed_exit
    while True:
        input_state = GPIO.input(exit_pin)
        if input_state == GPIO.LOW:
            if not button_was_pressed_exit:
                update_people_count(-1)
                button_was_pressed_exit = True
        else:
            button_was_pressed_exit = False
        await asyncio.sleep(0.05)

# Background task to send light sensor status and manage the alarm system
async def light_sensor_task():
    alarm_system_active = False
    outside_led_auto = False
    while True:
        light_status = GPIO.input(16)
        if light_status == GPIO.HIGH:  # Inverted logic
            if not alarm_system_active:
                alarm_system_active = True
                GPIO.output(7, GPIO.HIGH)  # Turn on the laser
                print("Night detected: Alarm system activated, laser turned on.")
            if not outside_led_auto:
                outside_led_auto = True
                leds[-1].on()  # Turn on the outside LED
                print("Night detected: Outside LED turned on.")
        else:
            if alarm_system_active:
                alarm_system_active = False
                GPIO.output(7, GPIO.LOW)  # Turn off the laser
                stop_sound()
                print("Daylight detected: Alarm system deactivated, laser turned off.")
            if outside_led_auto:
                outside_led_auto = False
                leds[-1].off()  # Turn off the outside LED
                print("Daylight detected: Outside LED turned off.")

        if alarm_system_active:
            await asyncio.sleep(0.05)
            laser_input = GPIO.input(12)
            if laser_input == GPIO.HIGH:
                play_sound()

        for ws in connected_websockets:
            await ws.send_json({"light_status": light_status, "outside_led_auto": outside_led_auto})

        await asyncio.sleep(0.1)

# Endpoint to get server status
@app.get("/status")
async def get_status():
    return {"status": "running"}

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.append(websocket)
    try:
        # Send initial states
        await websocket.send_json({"initial_states": led_states, "servo_state": servo_state, "people_count": people_count, "rc_motor_state": rc_motor_state})
        
        while True:
            # Receive toggle requests
            data = await websocket.receive_json()
            if "led_index" in data:
                toggle_led(data['led_index'])
                #update_single_lcd(int(data['led_index']))
                update_lcd()
                await websocket.send_json({"led_index": data['led_index'], "state": led_states[data['led_index']]})
                
            elif "servo" in data:
                toggle_servo()
                await websocket.send_json({"servo_state": servo_state})
            elif "rc_motor" in data:
                toggle_rc_motor()
                await websocket.send_json({"rc_motor_state": rc_motor_state})
    except WebSocketDisconnect:
        print("Client disconnected")
        connected_websockets.remove(websocket)

# Function to print a startup message and LED states on the LCD
@app.on_event("startup")
async def startup_event():
    lcd.clear()
    lcd.write_string("Server Started\n")
    time.sleep(2)
    lcd.clear()
    lcd.write_string("<G12_ARQUI1>    ")
    lcd.write_string("<VACAS_JUN_24>")
    time.sleep(10)
    lcd.clear()
    update_lcd()    
    # Start the light sensor task
    asyncio.create_task(light_sensor_task())
    # Start the entry and exit pin monitoring tasks
    asyncio.create_task(monitor_entry_pin())
    asyncio.create_task(monitor_exit_pin())

# Main entry point to start the server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
