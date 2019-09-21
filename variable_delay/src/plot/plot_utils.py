#!/usr/bin/env python

import math
import itertools
from matplotlib.colors import is_color_like
from cycler import cycler

#
# Function finds x limit for the graphs of the slotted data
# param [in] slotsNumber - number of slots
# param [in] slotSec     - slot size in seconds
# returns min x limit, max x limit
#
def get_x_limit(slotsNumber, slotSec):
    if slotsNumber == 0 or slotsNumber == 1:
        minLimit = -1
        maxLimit = 1
    else:
        minLimit = 0
        maxLimit = int(math.ceil((slotsNumber - 1) * slotSec))

    return minLimit, maxLimit


#
# Function finds marker for line graphs
# param [in] data - list with data to plot
# returns the marker
#
def get_marker(data):
    if len(data) == 1:
        marker = 'o'
    else:
        marker = None

    return marker


#
# Function is used to make plot labels have horizontal layout, rather than vertical (default)
# param [in] items - array of labels/handles should be supplied here
# param [in] ncol  - required number of labels per row
# returns labels/handles sorted in such a way that they will have horizontal layout
#
def flip(items, ncol):
    return list(itertools.chain(*[items[i::ncol] for i in range(ncol)]))


#
# Function checks if a string defines a color
# param [in] color - input string
# returns True if the string defines a color and False otherwise
#
def is_color(color):
    return is_color_like(color)


#
# Function makes the color cycle out of an array of colors
# param [in] colors - input array of colors
# returns the color cycle
#
def array_to_color_cycle(colors):
    return cycler('color', colors)


#
# Function gets the array of colors out of the color cycle
# param [in] colorCycle - input color cycle
# returns the array of colors
#
def color_cycle_to_array(colorCycle):
    return colorCycle.by_key()['color']
