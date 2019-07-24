#!/usr/bin/env python

from variable_delay.src.plot_type import PlotType
from variable_delay.src.layout import compute_per_flow
from variable_delay.src.layout_fields import SCHEME, DIRECTION
from variable_delay.src.metadata_fields import ALL_FLOWS, SORTED_LAYOUT

#
# Class of per-flow plots/stats
#
class PerFlowPlot(PlotType):
    #
    # Constructor
    #
    def __init__(self):
        PlotType.__init__(self)
        self.name = 'per-flow' # name of the type of plots/stats


    #
    # Method generates curves: flows merged into each curve and name of each curve.
    # param [in] metadata - metadata of flows
    # returns array of arrays of flows per curve, array of names of curves
    #
    def get_curves(self, metadata):
        flows  = range(0, metadata[ALL_FLOWS])
        layout = metadata[SORTED_LAYOUT]

        schemes    = compute_per_flow(SCHEME,    layout)
        directions = compute_per_flow(DIRECTION, layout)

        names = [ 'Flow {:d}: {} {}'.format(i + 1, schemes[i], directions[i]) for i in flows ]
        flows = [ [i] for i in flows ]

        return flows, names
