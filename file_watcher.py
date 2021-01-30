import sys, os
import json
from threading import Thread
from time import sleep

import win32api as wapi
import win32con as wcon
from win32event import INFINITE as inf
from win32event import WAIT_OBJECT_0, WAIT_FAILED, WaitForSingleObject

from flask import Flask, render_template
from flask_sockets import Sockets

from gevent import pywsgi
# from gevent import monkey
from geventwebsocket.handler import WebSocketHandler
# monkey.patch_all()

# C:\Users\[User]\AppData\Local\Packages\[PACKAGE ID]\LocalCache\Local\Netease\CloudMusic\webdata\file\history
# %appdata%/../local/netease/cloudmusic/webdata/file/
terminated = False
history_dir = None if len(sys.argv) == 1 else sys.argv[1]
if 'UWP' in history_dir.upper():
    for p, d, f in os.walk(os.path.join(os.getenv("appdata"),"../Local/Packages/")):
        if "CloudMusic" in d:
            # print( os.path.join(p,d[0]))
            history_dir = os.path.join(p, d[0]) +  "\\webdata\\file\\"
            break
if 'DESKTOP' in history_dir.upper():
    if os.path.exists(os.path.join(os.getenv("appdata"),"../local/netease/cloudmusic/webdata/file/")):
            history_dir = os.path.join(os.getenv("appdata"),"../local/netease/cloudmusic/webdata/file/")
if not history_dir:
    for p, d, f in os.walk(os.path.join(os.getenv("appdata"),"../Local/Packages/")):
        if "CloudMusic" in d:
            # print( os.path.join(p,d[0]))
            history_dir = os.path.join(p, d[0]) +  "\\webdata\\file\\"
            break
    if not history_dir:
        if os.path.exists(os.path.join(os.getenv("appdata"),"../local/netease/cloudmusic/webdata/file/")):
            history_dir = os.path.join(os.getenv("appdata"),"../local/netease/cloudmusic/webdata/file/")

if not history_dir or history_dir.upper() in ['UWP', 'DESKTOP']:
    print("Cannot find UWP Netease Cloudmusic history json directory, please specify by using", sys.argv[0], "[history json directory]")
    os.system("pause")
    exit(-1)

# After path successfully initialised
history = os.path.join(history_dir, "history")

# If running in standlone exe file
if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)
app_socket = Sockets(app=app)
users = []

def fileMonitor():
    global terminated
    changeHandle = wapi.FindFirstChangeNotification(history_dir, False, wcon.FILE_NOTIFY_CHANGE_LAST_WRITE)
    if not changeHandle:
        exit(-1)
    while not terminated:
        wait_object = WaitForSingleObject(changeHandle, inf)
        if wait_object == WAIT_OBJECT_0:
            print("Observed")
            on_file_change()
        elif wait_object == WAIT_FAILED:
            exit(-1)
        print("updated")
        wapi.FindNextChangeNotification(changeHandle)
    exit(-1)

def parseObj(obj):
    result = {
        "album_name": obj["track"]['album']['name'],
        "picUrl": obj["track"]['album']['picUrl'],
        "name": obj["track"]['name'],
        "artists": "/".join([i['name'] for i in obj["track"]['artists']]),
    }
    return result

last_song = None
def on_file_change():
    global last_song
    sleep(0.1)
    print("updating")
    with open(history, "rb") as his:
        data = his.read()
        obj = json.loads(data.decode(encoding="utf8", errors='ignore'))
        obj = parseObj(obj[0])
        if last_song != obj:
            last_song = obj
            wsocketPass()

def wsocketPass():
    global last_song, users
    for user in users:
        print("sending", last_song)
        if not user.closed:
            print(user)
            user.send(json.dumps(last_song))

# ping = False
# def _ping(ws):
#     global ping
#     msg = ws.receive()
#     if msg == "ACK" or msg == "PONG":
#         sleep(5)
#         ws.send("PING")
#         ping = False

@app.route("/")
def index():
    return render_template("index.html")

@app_socket.route("/conn")
def conn(ws):
    global last_song, users #, ping
    print("income connection")
    users += [ws]
    print("user connected")
    ws.send(json.dumps(last_song))
    while not ws.closed:
        # if not ping:
        #     ping = True
        #     Thread(target=_ping, args=(ws,)).start()
        msg = ws.receive()
        if msg == "ACK" or msg == "PONG":
            sleep(5)
            ws.send("PING")
    print("user disconnected")

if __name__ == "__main__":
    on_file_change()
    monitor = Thread(target=fileMonitor)
    monitor.setDaemon(True)
    monitor.start()
    server = pywsgi.WSGIServer(('0.0.0.0', 9999), app, handler_class=WebSocketHandler)
    server.serve_forever()
    # app.run(host="0.0.0.0", debug=False, port="9999")

