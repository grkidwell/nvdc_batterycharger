
from bokeh.models.widgets import Div,Paragraph
from bokeh.models import Panel
from bokeh.layouts import row

def description_tab():
    description = Div(text='''
<h2 id="duh2">NVDC Notebook Architecture\n</h2>
<h3 id="duh3">For the duration of the charging period, the instantaneous battery current will depend on the state of the whole system, which consists of:\n</h3>


<ul>
<li>Adaptor power rating - minus efficiency losses in the charger power train.</li>

<li>Charger max current - a new control loop which will protect the charger and inductor. </li>

<li>System load - adds to charger load and can reduce available charging current. If Psys &gt; Padaptor, then Ibattery will be &lt;0</li>

<li>Battery voltage - directly impacts System Voltage in the NVDC architecture. Also, for LiPO batteries, Vbat is current dependent. </li>

<li>Battery current - raises System Voltage through the voltage drop across battery charge path resistence</li>
</ul>

''',
    width=600, height=900)

    div_img = Div(text = "<img src='static/charger.png'>")

    layout = row(description,div_img)

    tab = Panel(child=layout, title = "Description")

    return tab