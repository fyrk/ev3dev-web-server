/**
 * This class represents one device (motor or sensor). 
 */
class Device {
    /**
     * @param {WebSocket} ws WebSocket to send changed values to 
     * @param {string} deviceType "motor" or "sensor"
     * @param {string} port port name as it is used internally, e.g. "ev3-ports:in1"
     * @param {string} portName human-readable port name, e.g. "1"
     * @param {{string: AttributeSetter}} attributeSetters Maps attribute names to AttributeSetter instances
     * @param {{string: AttributeSender}} attributeSenders Maps attribute names to AttributeSender instances
     */
    constructor(ws, deviceType, port, portName, attributeSetters, attributeSenders) {
        this.ws = ws;
        this.deviceType = deviceType;
        this.port = port;
        this.portName = portName;
        this.attributeSetters = attributeSetters;
        this.attributeSenders = attributeSenders;
        this.attributeValues = {};
    }

    onDeviceDisconnected() {
        this.attributeValues = {};
        for (let setter of Object.values(this.attributeSetters)) {
            setter.set(null);
            setter.setDisabled(true);
        }
        for (let sender of Object.values(this.attributeSenders)) {
            sender.setDisabled(true);
        }
    }

    /**
     * Update attribute values.
     * @param {{string: string}} values Maps attribute names to new values
     */
    updateValues(values) {
        for (let [attrName, attrValue] of Object.entries(values)) {
            const setter = this.attributeSetters[attrName];
            if (!setter) {
                console.error("Could not find attribute '" + attrName + "'");
                continue;
            }
            this.attributeValues[attrName] = setter.set(attrValue);
            setter.setDisabled(false);
        }
        for (let sender of Object.values(this.attributeSenders)) {
            sender.setDisabled(false);
        }
    }

    /**
     * This method is called by {@link AttributeSender}s when an attribute's value has been changed and should be sent to the server.
     * @param {string} attrName attribute name
     * @param {string} newValue new value for attribute
     */
    onUpdateValue(attrName, newValue) {
        this.attributeValues[attrName] = newValue;
        this.ws.send(JSON.stringify({ deviceType: this.deviceType, port: this.port, attributes: { [attrName]: newValue } }));
    }
}


/**
 * Used to set an attribute to the value sent by the server.
 */
class AttributeSetter {
    /**
     * @param {(HTMLElement|HTMLInputElement|HTMLSelectElement)} elem
     */
    constructor(device, elem) {
        this.device = device;
        this.elem = elem;
        this.set(null);
    }

    /**
     * Set the attribute's value to {@link value}. 
     * @param {string} value new value
     * @returns {string} the value that should be stored inside this.device.attributeValues
     */
    set(value) { 
        return value;
    }

    setDisabled(disabled) {
        this.elem.disabled = disabled;
    }
}

class InputAttributeSetter extends AttributeSetter {
    set(value) {
        if (value != null) {
            this.elem.value = value;
        } else {
            this.elem.value = this.elem.getAttribute("initValue");
        }
        return super.set(value);
    }
}
class PredefinedSelectAttributeSetter extends AttributeSetter {
    set(value) {
        if (value != null) {
            for (let i = 0; i < this.elem.options.length; i++) {
                if (this.elem.options[i].text === value) {
                    this.elem.selectedIndex = i;
                    break;
                }
            }
        } else {
            this.elem.selectedIndex = 0;
        }
        return super.set(value);
    }
}
class SelectAttributeSetter extends PredefinedSelectAttributeSetter {
    set(value) {
        while (this.elem.options.length > 0)
            this.elem.remove(0);
        if (value != null) {
            let values;
            let selected;
            if (Array.isArray(value)) {
                values = value;
                selected = null;
            } else {
                values = value["values"];
                selected = value["selected"];
            }
            for (let i = 0; i < values.length; i++) {
                const option = document.createElement("option");
                option.text = values[i];
                this.elem.appendChild(option);
                if (values[i] === selected) {
                    this.elem.selectedIndex = i;
                }
            }
            return selected;
        }
        return super.set(value);
    }
}
class DriverNameAttributeSetter extends AttributeSetter {
    set(value) {
        if (value != null) {
            // translate device name into a more human-readable form, for some sensors and motors
            const translated = {
                "lego-ev3-us": "EV3 Ultrasonic Sensor",
                "lego-ev3-gyro": "EV3 Gyro Sensor",
                "lego-ev3-color": "EV3 Color Sensor",
                "lego-ev3-touch": "EV3 Touch Sensor",
                "lego-ev3-ir": "EV3 Infrared Sensor",

                "lego-ev3-m-motor": "EV3 Medium Servo Motor",
                "lego-ev3-l-motor": "EV3 Large Servo Motor",

                "lego-nxt-temp": "NXT Temperature Sensor",
                "lego-nxt-light": "NXT Light Sensor",
                "lego-nxt-sound": "NXT Sound Sensor",
                "lego-nxt-us": "NXT Ultrasonic Sensor"
            }[value] || value;
            this.elem.textContent = translated + " (" + this.device.portName + ")";
        } else {
            this.elem.textContent = "Port " + this.device.portName;
        }
        return super.set(value);
    }
}
class MotorPositionAttributeSetter extends AttributeSetter {
    set(value) {
        if (value != null) {
            this.elem.textContent = value;
        } else {
            this.elem.textContent = "<None>";
        }
        return super.set(value);
    }
}
class SensorValuesAttributeSetter extends AttributeSetter {
    set(value) {
        if (value != null) {
            let translated = value;
            try {
                // translate values of some sensors into a more readable form
                switch (this.device.attributeValues["driver_name"]) {
                    case "lego-ev3-color":
                        if (this.device.attributeValues["mode"] === "COL-COLOR") {
                            translated = {
                                "0": '<span class="circle"></span>No Color (0)',
                                "1": '<span class="circle black-circle"></span>Black (1)',
                                "2": '<span class="circle blue-circle"></span>Blue (2)',
                                "3": '<span class="circle green-circle"></span>Green (3)',
                                "4": '<span class="circle yellow-circle"></span>Yellow (4)',
                                "5": '<span class="circle red-circle"></span>Red (5)',
                                "6": '<span class="circle white-circle-with-border"></span>White (6)',
                                "7": '<span class="circle brown-circle"></span>Brown (7)'
                            }[value] || value;
                        }
                        break;
                    case "lego-ev3-touch":
                        translated = {
                            "0": "Released (0)",
                            "1": "Pressed (1)"
                        }[value] || value;
                        break;
                    case "lego-ev3-ir":
                        if (this.device.attributeValues["mode"] === "IR-REMOVE") {
                            const values = value.split(' ');
                        }
                }
            } catch (e) {
                console.error(e);
            }
            
            this.elem.innerHTML = translated;
        } else {
            this.elem.textContent = "<None>";
        }
        return super.set(value);
    }
}


/**
 * Used to send an attribute to the server
 */
class AttributeSender {
    constructor(device, name, inputElem) {
        this.device = device;
        this.name = name;
        this.inputElem = inputElem;
    }

    getValue() { }

    setDisabled(disabled) {
        this.inputElem.disabled = disabled;
    }
}

class NormalAttributeSender extends AttributeSender {
    constructor(device, name, inputElem, event) {
        super(device, name, inputElem);
        this.inputElem.addEventListener(event, () => this.device.onUpdateValue(this.name, this.getValue()));
    }
}
class InputAttributeSender extends NormalAttributeSender {
    constructor(device, name, inputElem) {
        super(device, name, inputElem, "input");
    }
    getValue() {
        return this.inputElem.value;
    }
}
class SelectAttributeSender extends NormalAttributeSender {
    constructor(device, name, inputElem) {
        super(device, name, inputElem, "change");
    }
    getValue() {
        return this.inputElem.options[this.inputElem.selectedIndex].text;
    }
}

class AttributeSenderOnButton extends AttributeSender {
    constructor(device, name, inputElem, buttonElem) {
        super(device, name, inputElem);
        this.buttonElem = buttonElem;
        this.buttonElem.addEventListener("click", () => this.device.onUpdateValue(this.name, this.getValue()));
    }

    setDisabled(disabled) {
        super.setDisabled(disabled);
        this.buttonElem.disabled = disabled;
    }
}
class InputAttributeSenderOnButton extends AttributeSenderOnButton {
    getValue() {
        return this.inputElem.value;
    }
}
class SelectAttributeSenderOnButton extends AttributeSenderOnButton {
    getValue() {
        return this.inputElem.options[this.inputElem.selectedIndex].text;
    }
}

/**
 * Represents one motor port
 */
class MotorDevice extends Device {
    /**
     * @param {WebSocket} ws see {@link Device}
     * @param {string} port see {@link Device}
     * @param {string} portName see {@link Device}
     * @param {HTMLElement} card The HTMLElement that represents this port
     */
    constructor(ws, port, portName, card) {
        super(ws, "motor", port, portName, {}, {});
        this.attributeSetters = {
            "position": new MotorPositionAttributeSetter(this, card.getElementsByClassName("positionDisplay")[0]),
            "driver_name": new DriverNameAttributeSetter(this, card.getElementsByClassName("port")[0]),
            "duty_cycle_sp": new InputAttributeSetter(this, card.getElementsByClassName("duty_cycle_sp")[0]),
            "polarity": new PredefinedSelectAttributeSetter(this, card.getElementsByClassName("polarity")[0]),
            "position_sp": new InputAttributeSetter(this, card.getElementsByClassName("position_sp")[0]),
            "speed_sp": new InputAttributeSetter(this, card.getElementsByClassName("speed_sp")[0]),
            "ramp_up_sp": new InputAttributeSetter(this, card.getElementsByClassName("ramp_up_sp")[0]),
            "ramp_down_sp": new InputAttributeSetter(this, card.getElementsByClassName("ramp_down_sp")[0]),
            "stop_action": new SelectAttributeSetter(this, card.getElementsByClassName("stop_action")[0]),
            "time_sp": new InputAttributeSetter(this, card.getElementsByClassName("time_sp")[0]),
            "command": new SelectAttributeSetter(this, card.getElementsByClassName("command")[0])
        };
        this.attributeSenders = {
            "position": new InputAttributeSenderOnButton(this, "position", card.getElementsByClassName("positionInput")[0], card.getElementsByClassName("sendPositionButton")[0]),
            "duty_cycle_sp": new InputAttributeSender(this, "duty_cycle_sp", card.getElementsByClassName("duty_cycle_sp")[0]),
            "polarity": new SelectAttributeSender(this, "polarity", card.getElementsByClassName("polarity")[0]),
            "position_sp": new InputAttributeSender(this, "position_sp", card.getElementsByClassName("position_sp")[0]),
            "speed_sp": new InputAttributeSender(this, "speed_sp", card.getElementsByClassName("speed_sp")[0]),
            "ramp_up_sp": new InputAttributeSender(this, "ramp_up_sp", card.getElementsByClassName("ramp_up_sp")[0]),
            "ramp_down_sp": new InputAttributeSender(this, "ramp_down_sp", card.getElementsByClassName("ramp_down_sp")[0]),
            "stop_action": new SelectAttributeSender(this, "stop_action", card.getElementsByClassName("stop_action")[0]),
            "time_sp": new InputAttributeSender(this, "time_sp", card.getElementsByClassName("time_sp")[0]),
            "command": new SelectAttributeSenderOnButton(this, "command", card.getElementsByClassName("command")[0], card.getElementsByClassName("sendCommandButton")[0])
        };
    }
}

/**
 * Represents one sensor port
 */
class SensorDevice extends Device {
    /**
     * @param {WebSocket} ws see {@link Device}
     * @param {string} port see {@link Device}
     * @param {string} portName see {@link Device}
     * @param {HTMLElement} card The HTMLElement that represents this port
     */
    constructor(ws, port, portName, card) {
        super(ws, "sensor", port, portName, {}, {});
        this.attributeSetters = {
            "values": new SensorValuesAttributeSetter(this, card.getElementsByClassName("values")[0]),
            "driver_name": new DriverNameAttributeSetter(this, card.getElementsByClassName("port")[0]),
            "mode": new SelectAttributeSetter(this, card.getElementsByClassName("mode")[0]),
            "command": new InputAttributeSetter(this, card.getElementsByClassName("command")[0])
        };
        this.attributeSenders = {
            "mode": new SelectAttributeSender(this, "mode", card.getElementsByClassName("mode")[0]),
            "command": new SelectAttributeSenderOnButton(this, "command", card.getElementsByClassName("command")[0], card.getElementsByClassName("sendCommandButton")[0])
        };
    }
}


window.onload = () => {
    const SENSOR_TEMPLATE = document.getElementById("sensor-template");
    const MOTOR_TEMPLATE = document.getElementById("motor-template");

    const SENSOR_CONTAINER = document.getElementById("sensors-container");
    const MOTOR_CONTAINER = document.getElementById("motors-container");

    const alertWebsocketClosed = document.getElementById("alert-websocket-closed");
    
    const SENSOR_PORTS = [
        ["ev3-ports:in1", "1"],
        ["ev3-ports:in2", "2"],
        ["ev3-ports:in3", "3"],
        ["ev3-ports:in4", "4"]
    ];
    const MOTOR_PORTS = [
        ["ev3-ports:outA", "A"],
        ["ev3-ports:outB", "B"],
        ["ev3-ports:outC", "C"],
        ["ev3-ports:outD", "D"]
    ];

    let ws = null;

    try {
        ws = new WebSocket("ws://" + window.location.hostname + ":8000/ev3-info");
    } catch (error) {
        console.error(error);
        alertWebsocketClosed.hidden = false;
    }
    
    /** @type {string: Device} Maps port names to devices */
    const devices = {};
    
    if (ws != null) {
        ws.onopen = event => console.log("websocket opened", event);
        ws.onclose = event => {
            console.log("websocket closed", event);
            alertWebsocketClosed.hidden = false;
        }
        ws.onmessage = event => {
            const data = JSON.parse(event.data);
            for (let [port, deviceData] of Object.entries(data)) {
                if (port === "disconnected_devices") {
                    for (let disconnectedPort of deviceData) {
                        console.log("device disconnected", disconnectedPort);
                        devices[disconnectedPort].onDeviceDisconnected();
                    }
                } else {
                    devices[port].updateValues(deviceData);
                }
            }
        };
    }

    for (let [port, portName] of SENSOR_PORTS) {
        const newCard = SENSOR_TEMPLATE.content.firstElementChild.cloneNode(true);
        devices[port] = new SensorDevice(ws, port, portName, newCard);
        SENSOR_CONTAINER.appendChild(newCard);
    }

    for (let [port, portName] of MOTOR_PORTS) {
        const newCard = MOTOR_TEMPLATE.content.firstElementChild.cloneNode(true);
        devices[port] = new MotorDevice(ws, port, portName, newCard);
        MOTOR_CONTAINER.appendChild(newCard);
    }
};
