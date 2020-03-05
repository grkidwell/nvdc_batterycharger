

from flask import Flask, render_template
from bokeh.embed import server_document

from bokeh.models.widgets import Tabs

from bokeh.server.server import Server
from bokeh.themes import Theme
from tornado.ioloop import IOLoop

# Each tab is drawn by one script
from scripts.chargetime import chargetime_tab
from scripts.description import description_tab

import os

fileDir = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

def modify_doc(doc):

    # Create each of the tabs
    tab1 = description_tab()
    tab2 = chargetime_tab()


    # Put all the tabs into one application
    tabs = Tabs(tabs = [tab1,tab2])

    doc.add_root(tabs)

    doc.theme = Theme(filename=fileDir+"/"+"misc/"+"theme.yaml")


@app.route('/', methods=['GET'])
def bkapp_page():
    script = server_document('http://localhost:5006/bkapp')
    return render_template("embed.html", script=script, template="Flask")


def bk_worker():
    # Can't pass num_procs > 1 in this configuration. If you need to run multiple
    # processes, see e.g. flask_gunicorn_embed.py
    server = Server({'/bkapp': modify_doc}, io_loop=IOLoop(), allow_websocket_origin=["localhost:8000"])
    server.start()
    server.io_loop.start()

from threading import Thread
Thread(target=bk_worker).start()

if __name__ == '__main__':
    print('Opening single process Flask app with embedded Bokeh application on http://localhost:8000/')
    print()
    print('Multiple connections may block the Bokeh app in this configuration!')
    print('See "flask_gunicorn_embed.py" for one way to run multi-process')
    app.run(host='0.0.0.0',port=8000)
