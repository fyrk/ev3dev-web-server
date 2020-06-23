ev3dev-web-server
=================

This simple web server for [ev3dev](https://github.com/ev3dev/ev3dev) enables the user to:

* Monitor sensor values and motor positions
* Control motors by sending commands
* Changing sensor mode

This project consists of two components:

1. The actual web server, [a Python script](server.py) which sends values to clients and receives commands through *WebSockets*.
2. A [website](website/) which receives values through JavaScript and sends values to the server.


Getting Started
---------------

1. Copy this repository to your ev3dev device, e.g. by cloning.
2. Install `tornado`: 
```
$ sudo apt-get install python3-tornado
```
3. Run `python3 server.py`.
4. In a browser, open `<ev3dev ip>:8000`.


Licensing
-------

This project is licensed under the terms of the MIT license, see [LICENSE](LICENSE).

This project uses Bootstrap v4.4.1, see [website/bootstrap.min.css](website/bootstrap.min.css).
