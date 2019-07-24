#!/usr/bin/env python

from variable_delay.src.plot_type import PlotType, PlotTypeError
from variable_delay.src.layout_fields import SCHEME, DIRECTION
from variable_delay.src.layout import compute_per_flow
from variable_delay.src.metadata_fields import ALL_FLOWS, SORTED_LAYOUT

FLOW  = 'flow'
FLOWS = 'flows'


#
# Class of per-subset plots/stats
#
class PerSubsetPlot(PlotType):
    ALLOWED_FIELDS = [ SCHEME, DIRECTION ] # layout fields allowed

    #
    # Constructor
    # param [in] fields - layout fields by which flows should be divided into subsets
    # throws PlotTypeError
    #
    def __init__(self, fields):
        PlotType.__init__(self)

        if not isinstance(fields, list) or len(fields) == 0:
            raise PlotTypeError('Non-empty list of layout fields should be supplied\n'
                                'Allowed fields: %s' % PerSubsetPlot.ALLOWED_FIELDS)

        for field in fields:
            if field not in PerSubsetPlot.ALLOWED_FIELDS:
                raise PlotTypeError('This is not a layout field allowed: \'%s\'\n'
                                    'Allowed fields: %s'% (field, PerSubsetPlot.ALLOWED_FIELDS))

        self.fields = fields                         # layout fields to divide flows
        self.name   = 'per-' + '-'.join(self.fields) # name of the type of plots/stats


    #
    # Method generates curves: list of flows merged into each curve and name of each curve.
    # param [in] metadata - metadata of flows
    # returns array of arrays of flow indices per curve, array of names of curves
    #
    def get_curves(self, metadata):
        layout = metadata[SORTED_LAYOUT]
        values = [ compute_per_flow(field, layout) for field in self.fields ]
        curves = { }

        for flow in range(0, metadata[ALL_FLOWS]):
            curveName = []

            for index, fieldValues in enumerate(values):
                value = self.layout_value_to_str(fieldValues[flow], self.fields[index])
                curveName.append(value)

            curveName = ' '.join(curveName)

            curves.setdefault(curveName, []).append(flow)

        curves = sorted(curves.items(), key=lambda item: item[1][0]) # sort by the first flow index

        flows = []
        names = []

        for tuple in curves:
            curveName = tuple[0]
            flowsList = tuple[1]
            flowsWord = FLOW if len(flowsList) == 1 else FLOWS

            names.append("{} : {:d} {}".format(curveName, len(flowsList), flowsWord))
            flows.append(flowsList)

        return flows, names


    #
    # Method converts layout value to a string to put it into the name of the curve in plots/stats.
    # param [in] value - value of the layout field
    # param [in] field - layout field name
    # returns the string representation of the value of the layout field
    #
    def layout_value_to_str(self, value, field):
        if   field == SCHEME:
            return value # string already
        elif field == DIRECTION:
            return value # string already
