'''
The MIT License (MIT)

Copyright (C) 2014, 2015 Seven Watt <info@sevenwatt.com>
<http://www.sevenwatt.com>

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


--------


I (Florian Rädiker) have updated this script to Python 3. 
'''

from http.server import SimpleHTTPRequestHandler, HTTPServer
import struct
import traceback
from base64 import b64encode
from hashlib import sha1
from email.message import Message
from io import StringIO
import errno, socket #for socket exceptions
import threading

class WebSocketError(Exception):
    pass

class HTTPWebSocketsHandler(SimpleHTTPRequestHandler):
    _ws_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
    _opcode_continu = 0x0
    _opcode_text = 0x1
    _opcode_binary = 0x2
    _opcode_close = 0x8
    _opcode_ping = 0x9
    _opcode_pong = 0xa

    mutex = threading.Lock()
    
    def on_ws_message(self, message):
        """Override this handler to process incoming websocket messages."""
        pass
        
    def on_ws_connected(self):
        """Override this handler."""
        pass
        
    def on_ws_closed(self):
        """Override this handler."""
        pass
        
    def send_message(self, message):
        self._send_message(self._opcode_text, message)

    def setup(self):
        SimpleHTTPRequestHandler.setup(self)
        self.connected = False
                
    # def finish(self):
        # #needed when wfile is used, or when self.close_connection is not used
        # #
        # #catch errors in SimpleHTTPRequestHandler.finish() after socket disappeared
        # #due to loss of network connection
        # try:
            # SimpleHTTPRequestHandler.finish(self)
        # except (socket.error, TypeError) as err:
            # self.log_message("finish(): Exception: in SimpleHTTPRequestHandler.finish(): %s" % str(err.args))

    # def handle(self):
        # #needed when wfile is used, or when self.close_connection is not used
        # #
        # #catch errors in SimpleHTTPRequestHandler.handle() after socket disappeared
        # #due to loss of network connection
        # try:
            # SimpleHTTPRequestHandler.handle(self)
        # except (socket.error, TypeError) as err:
            # self.log_message("handle(): Exception: in SimpleHTTPRequestHandler.handle(): %s" % str(err.args))

    def checkAuthentication(self):
        auth = self.headers.get('Authorization')
        if auth != "Basic %s" % self.server.auth:
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Plugwise"')
            self.end_headers()
            return False
        return True
        
    def do_GET(self):
        if self.headers.get("Upgrade", None) == "websocket":
            self._handshake()
            #This handler is in websocket mode now.
            #do_GET only returns after client close or socket error.
            self._read_messages()
        else:
            SimpleHTTPRequestHandler.do_GET(self)
                          
    def _read_messages(self):
        while self.connected == True:
            try:
                self._read_next_message()
            except (socket.error, WebSocketError) as e:
                #websocket content error, time-out or disconnect.
                self.log_message("RCV: Close connection: Socket Error %s" % str(e.args))
                self._ws_close()
            except Exception as err:
                #unexpected error in websocket connection.
                self.log_error("RCV: Exception: in _read_messages: %s" % str(err.args))
                self._ws_close()
        
    def _read_next_message(self):
        #self.rfile.read(n) is blocking.
        #it returns however immediately when the socket is closed.
        try:
            self.opcode = int.from_bytes(self.rfile.read(1), "big") & 0x0F
            length = int.from_bytes(self.rfile.read(1), "big") & 0x7F
            if length == 126:
                length = struct.unpack(">H", self.rfile.read(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self.rfile.read(8))[0]
            masks = [byte for byte in self.rfile.read(4)]
            decoded = bytearray()
            for char in self.rfile.read(length):
                decoded.append(char ^ masks[len(decoded) % 4])
            self._on_message(decoded)
        except (struct.error, TypeError):
            #catch exceptions from ord() and struct.unpack()
            traceback.print_exc()
            if self.connected:
                raise WebSocketError("Websocket read aborted while listening")
            else:
                #the socket was closed while waiting for input
                self.log_error("RCV: _read_next_message aborted after closed connection")
                pass
        
    def _send_message(self, opcode, message):
        try:
            #use of self.wfile.write gives socket exception after socket is closed. Avoid.
            payload = bytearray()
            payload.append(0x80 + opcode)
            length = len(message)
            if length <= 125:
                payload.append(length)
            elif length >= 126 and length <= 65535:
                payload.append(126)
                payload.extend(struct.pack(">H", length))
            else:
                payload.append(127)
                payload.extend(struct.pack(">Q", length))
            if length > 0:
                payload.extend(message)
            self.request.send(payload)
        except socket.error as e:
            traceback.print_exc()
            #websocket content error, time-out or disconnect.
            self.log_message("SND: Close connection: Socket Error %s" % str(e.args))
            self._ws_close()
        except Exception as err:
            traceback.print_exc()
            #unexpected error in websocket connection.
            self.log_error("SND: Exception: in _send_message: %s" % str(err.args))
            self._ws_close()

    def _handshake(self):
        headers=self.headers
        if headers.get("Upgrade", None) != "websocket":
            return
        key = headers['Sec-WebSocket-Key']
        k = key.encode("ascii") + self._ws_GUID.encode("ascii")  # from https://github.com/pikhovkin/simple-websocket-server/blob/master/simple_websocket_server/__init__.py
        k_s = b64encode(sha1(k).digest()).decode("ascii")
        self.send_response(101, 'Switching Protocols')
        self.send_header('Upgrade', 'websocket')
        self.send_header('Connection', 'Upgrade')
        self.send_header('Sec-WebSocket-Accept', k_s)
        self.end_headers()
        self.connected = True
        #self.close_connection = 0
        self.on_ws_connected()
    
    def _ws_close(self):
        #avoid closing a single socket two time for send and receive.
        self.mutex.acquire()
        try:
            if self.connected:
                self.connected = False
                #Terminate BaseHTTPRequestHandler.handle() loop:
                self.close_connection = 1
                #send close and ignore exceptions. An error may already have occurred.
                try: 
                    self._send_close()
                except:
                    pass
                self.on_ws_closed()
            else:
                self.log_message("_ws_close websocket in closed state. Ignore.")
                pass
        finally:
            self.mutex.release()
            
    def _on_message(self, message):
        #self.log_message("_on_message: opcode: %02X msg: %s" % (self.opcode, message))
        
        # close
        if self.opcode == self._opcode_close:
            self.connected = False
            #Terminate BaseHTTPRequestHandler.handle() loop:
            self.close_connection = 1
            try:
                self._send_close()
            except:
                pass
            self.on_ws_closed()
        # ping
        elif self.opcode == self._opcode_ping:
            self._send_message(self._opcode_pong, message)
        # pong
        elif self.opcode == self._opcode_pong:
            pass
        # data
        elif (self.opcode == self._opcode_continu or 
                self.opcode == self._opcode_text or 
                self.opcode == self._opcode_binary):
            self.on_ws_message(message)

    def _send_close(self):
        #Dedicated _send_close allows for catch all exception handling
        msg = bytearray()
        msg.append(0x80 + self._opcode_close)
        msg.append(0x00)
        self.request.send(msg)


#main program and imports for standalone purpose       
import sys
from socketserver import ThreadingMixIn

if len(sys.argv) > 1:
    port = int(sys.argv[1])
else:
    port = 8000
if len(sys.argv) > 2:
    secure = str(sys.argv[2]).lower()=="secure"
else:
    secure = False
if len(sys.argv) > 3:
    credentials = str(sys.argv[3])
else:
    credentials = ""

class WSSimpleEcho(HTTPWebSocketsHandler):
    def on_ws_message(self, message):
        if message is None:
            message = ''
        # echo message back to client
        self.send_message(str(message))
        self.log_message('websocket received "%s"',str(message))

    def on_ws_connected(self):
        self.log_message('%s','websocket connected')

    def on_ws_closed(self):
        self.log_message('%s','websocket closed')

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


if __name__ == '__main__':
    import ssl

    def _ws_main():
        try:
            #Replace WSSimpleEcho with your own subclass of HTTPWebSocketHandler
            server = ThreadedHTTPServer(('', port), WSSimpleEcho)
            server.daemon_threads = True
            server.auth = b64encode(credentials)
            if secure:
                server.auth = b64encode(credentials)
                server.socket = ssl.wrap_socket (server.socket, certfile='./server.pem', server_side=True)
                print('started secure https server at port %d' % (port,))
            else: 
                print('started http server at port %d' % (port,))
            server.serve_forever()
        except KeyboardInterrupt:
            print('^C received, shutting down server')
            server.socket.close()

    _ws_main()