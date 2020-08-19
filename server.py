#!/usr/bin/env python3
print("Starting server...")
from ev3dev2.console import Console
Console("Lat15-Terminus12x6")
print("Importing modules (this may take a while)...")
import time
t1 = time.perf_counter()
import json
import os
import subprocess
import time
import traceback
from base64 import b64decode
from shutil import which
from socket import gethostname
from threading import Thread, Lock

import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket
from ev3dev2.led import Leds
from ev3dev2.motor import list_motors, Motor, MoveJoystick, OUTPUT_B, OUTPUT_C
from ev3dev2.sensor import list_sensors, Sensor
t2 = time.perf_counter()
print("Imported in", t2-t1)


# has auth is True if users should be logged in to access the server
HAS_AUTH = (os.path.exists(".htpasswd")  # check that password file exists ...
            and which("htpasswd") is not None)  # ... and that program 'htpasswd' exists

class BasicAuthHandler(tornado.web.RequestHandler):
    def prepare(self):
        if HAS_AUTH:
            def request_auth():
                self.set_header("WWW-Authenticate", 'Basic realm="Connect to ' + gethostname() + '"')
                self.set_status(401)
                self.finish()
                tornado.web.Finish()
            auth = self.request.headers.get("Authorization")
            if auth is None or not auth.startswith("Basic "):
                return request_auth()
            try:
                decoded = b64decode(auth.split(maxsplit=1)[1])
            except Exception:
                return request_auth()
            user, pwd = decoded.split(b":", 1)
            try:
                proc = subprocess.run(["htpasswd", "-i", "-v", ".htpasswd", user], timeout=1, input=pwd)
            except subprocess.TimeoutExpired:
                return request_auth()
            if proc.returncode != 0:
                return request_auth()


LEDS = Leds()
LEDS.all_off()
LEDS.reset()


move_joystick = None
motors = {}
old_joystick_left_port = None
old_joystick_right_port = None
old_motor_1_port = None
old_motor_2_port = None

class EV3InfoHandler(BasicAuthHandler, tornado.websocket.WebSocketHandler):
    websockets = set()
    websockets_lock = Lock()

    def open(self):
        with EV3InfoHandler.websockets_lock:
            EV3InfoHandler.websockets.add(self)
        self.write_message(get_info(set(), set(), True)[0])
        self.write_message("next")  # inform client that it is allowed to send a new message
    
    def on_close(self):
        with EV3InfoHandler.websockets_lock:
            EV3InfoHandler.websockets.remove(self)

    def on_message(self, messages):
        global move_joystick
        try:
            print("got messages", messages)
            for message in json.loads(messages):
                type_ = message["type"]
                if type_ == "rc-joystick":
                    if message["leftPort"] != old_joystick_left_port or message["rightPort"] != old_joystick_right_port:
                        move_joystick = MoveJoystick(message["leftPort"], message["rightPort"])
                    if message["x"] == 0 and message["y"] == 0:
                        move_joystick.off(brake=False)
                    else:
                        move_joystick.on(message["x"], message["y"], 1)
                elif type_ == "rc-motor":
                    if message["port"] in motors:
                        motor = motors[message["port"]]
                    else:
                        motor = motors[message["port"]] = Motor(message["port"])
                    motor.on(message["speed"]*100)
                elif type_ == "sensor":
                    port = message["port"]
                    attributes = message["attributes"]
                    device = Sensor(port)
                    for name, value in attributes.items():
                        setattr(device, name, value)
                    # send changes to other clients
                    EV3InfoHandler.send_to_all(json.dumps({port: attributes}), {self})
                elif type_ == "motor":
                    port = message["port"]
                    attributes = message["attributes"]
                    device = Motor(port)
                    for name, value in attributes.items():
                        setattr(device, name, value)
                    # send changes to other clients
                    EV3InfoHandler.send_to_all(json.dumps({port: attributes}), {self})
                elif type_ == "led":
                    port = message["port"]
                    attributes = message["attributes"]
                    led_group = port.split(":")[1].lower()
                    for color_name, brightness in attributes.items():
                        LEDS.leds[color_name + "_" + led_group].brightness_pct = float(brightness)
                    # send changes to other clients
                    EV3InfoHandler.send_to_all(json.dumps({port: attributes}), {self})
                else:
                    raise ValueError("Unknown message type '" + type_ + "'")
        except Exception:
            traceback.print_exc()
        self.send_to_all("next")
    
    @classmethod
    def send_to_all(cls, message, exclude_websockets=None):
        with cls.websockets_lock:
            for websocket in cls.websockets:
                if not exclude_websockets or websocket not in exclude_websockets:
                    try:
                        websocket.write_message(message)
                    except Exception:
                        traceback.print_exc()


"""
Returns a string containing a JSON object which describes the current motor/sensor values in the following format:
    {
        "<address (e.g. "ev3-ports:in1")>": {
            // for both sensors and motors:
            "driver_name": "<driver name>",
            "command": [<list of possible commands>],
            // for sensors:
            "values": "<current sensor values, separated by space (max. 8)>",
            "mode": {
                "selected": "<currently selected mode>],
                "values": [<list of possible modes>]
            },
            // for motors:
            "position": "<current motor position>",
            "duty_cycle_sp": "<duty cycle setpoint>",
            "polarity": "normal" or "inversed",
            "position_sp": "position setpoint",
            "speed_sp": "speed setpoint",
            "ramp_up_sp": "ramp up setpoint",
            "ramp_down_sp": "ramp down setpoint",
            "stop_action": {
                "selected": "<currently selected stop_action>",
                "values": [<list of possible stop_actions>]
            },
            "time_sp": "time setpoint",
        }
    }
Parameters 'old_sensor_addressse' and 'old_motor_addresses' are sets of previously available adresses. 
If an address was previously available, only "values" attribute (for sensors) or "position" attribute (for motors) is included.
This is because these are the only properties that change while the user views the page. 
If 'all_info' is True, additional info is added that clients need when they connect for the first time: Currently, this is only LED brightnesses. 
When a WebSocket first connects with the server, get_info(set(), set()) is called so that initially the client receives all attributes (see EV3InfoHandler.open). 

get_info returns: (string containing JSON object, new sensor addresses (for use in the next call of get_info), new motor addresses (for use in the next call of get_info)).
"""
def get_info(old_sensor_addresses, old_motor_addresses, all_info=False):
    info = {"disconnected_devices": []}
    if all_info:
        for group_name, leds in LEDS.led_groups.items():
            info["led:" + group_name] = {led.desc.split("_")[0]: led.brightness_pct for led in leds}
    sensor_addresses = set()
    for sensor in list_sensors("*"):
        try:
            address = sensor.address
            if address.count(":") > 1:
                # addresses for i2c sensors end with ':i2c*', remove this
                address = address[:address.index(":", address.index(":")+1)]
            if address in old_sensor_addresses:
                old_sensor_addresses.remove(address)
                info[address] = {
                    "values": " ".join(str(sensor.value(i)) for i in range(sensor.num_values))
                }
            else:
                info[address] = {
                    "driver_name": sensor.driver_name,
                    "mode": {
                        "values": sensor.modes,
                        "selected": sensor.mode
                    },
                    "command": sensor.commands,
                    "values": " ".join(str(sensor.value(i)) for i in range(sensor.num_values)),
                    #"decimals": sensor.decimals,
                }
            sensor_addresses.add(address)
        except Exception:
            traceback.print_exc()
    info["disconnected_devices"].extend(old_sensor_addresses)
    motor_addresses = set()
    for motor in list_motors("*"):
        try:
            address = motor.address
            if address in old_motor_addresses:
                old_motor_addresses.remove(address)
                info[address] = {
                    "position": motor.position
                }
            else:
                info[address] = {
                    "driver_name": motor.driver_name,
                    "duty_cycle_sp": motor.duty_cycle_sp,
                    "polarity": motor.polarity,
                    "position": motor.position,
                    "position_sp": motor.position_sp,
                    "speed_sp": motor.speed_sp,
                    "ramp_up_sp": motor.ramp_up_sp,
                    "ramp_down_sp": motor.ramp_down_sp,
                    "stop_action": {
                        "values": motor.stop_actions,
                        "selected": motor.stop_action
                    },
                    "time_sp": motor.time_sp,
                    "command": motor.commands
                }
            motor_addresses.add(address)
        except Exception:
            traceback.print_exc()
    info["disconnected_devices"].extend(old_motor_addresses)
    content = json.dumps(info).encode("utf-8")
    return content, sensor_addresses, motor_addresses


def send_info():
    old_sensor_addresses = set()
    old_motor_addresses = set()
    while True:
        if len(EV3InfoHandler.websockets) == 0:
            print("Waiting for clients to connect...")
            while len(EV3InfoHandler.websockets) == 0:
                time.sleep(0.5)
            print("Clients connected!")
        content, old_sensor_addresses, old_motor_addresses = get_info(old_sensor_addresses, old_motor_addresses)
        EV3InfoHandler.send_to_all(content)
        time.sleep(0.1)


class StaticFiles(BasicAuthHandler, tornado.web.StaticFileHandler):
    def set_extra_headers(self, path):
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")


if __name__ == "__main__":
    tornado.options.define("port", default=8000, help="run on the given port", type=int)
    tornado.options.parse_command_line()
    static_files = os.path.join(os.path.dirname(__file__), "website")
    app = tornado.web.Application([
            (r"/ev3-info", EV3InfoHandler),
            (r"/(.*)", StaticFiles, {"path": static_files, "default_filename": "index.html"})
        ],
        static_path=os.path.join(os.path.dirname(__file__), "website")
    )
    app.listen(tornado.options.options.port)
    print("Serving on port", tornado.options.options.port)
    if HAS_AUTH:
        print("Basic auth is required when connecting")
    ioloop = tornado.ioloop.IOLoop.current()
    Thread(target=ioloop.start).start()
    Thread(target=send_info).start()
