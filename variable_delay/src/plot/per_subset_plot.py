#!/usr/bin/env python

from variable_delay.src.plot.plot_type import PlotType, PlotTypeError
from variable_delay.src.layout.layout_fields import SCHEME, DIRECTION
from variable_delay.src.layout.layout import compute_per_flow
from variable_delay.src.plot.curve import Curve

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

        # name of the type of plots/stats
        self.name = 'per-' + '-'.join(fields)

        # layout fields to divide flows
        self.fields = fields

        # curve's label prefix notation
        self.notation = 'Label notation: <{}> : <flows number> flows'.\
            format('> <'.join(self.fields))


    #
    # Method generates curves: list of flows merged into each curve and name of each curve.
    # param [in] layout - layout of flows
    # param [in] flows  - flows to divide into curves
    # returns curves
    #
    def get_curves(self, layout, flows):
        values = [ compute_per_flow(field, layout) for field in self.fields ]
        curves = { }

        for flowId, flow in enumerate(flows):
            curveName = []

            for index, fieldValues in enumerate(values):
                value = self.layout_value_to_str(fieldValues[flowId], self.fields[index])
                curveName.append(value)

            curveName = ' '.join(curveName)

            curves.setdefault(curveName, []).append(flow)

        curves = sorted(curves.items(), key=lambda item: item[1][0].id) # sort by the first flow id

        curvesArray = []

        for tuple in curves:
            curveName = tuple[0]
            flowsList = tuple[1]
            flowsWord = FLOW if len(flowsList) == 1 else FLOWS
            name      = '{} : {:d} {}'.format(curveName, len(flowsList), flowsWord)

            curvesArray.append(Curve(flowsList, name))

        return curvesArray


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
