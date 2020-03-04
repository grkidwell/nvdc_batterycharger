
# os methods for manipulating paths
from os.path import dirname, join

# Bokeh basics 
from bokeh.io import curdoc
from bokeh.models.widgets import Tabs


# Each tab is drawn by one script
from scripts.chargetime import chargetime_tab


# Create each of the tabs
tab1 = chargetime_tab()

# Put all the tabs into one application
tabs = Tabs(tabs = [tab1])

# Put the tabs in the current document for display
curdoc().add_root(tabs)


