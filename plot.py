#!/usr/bin/env python

import sys
import os
import argparse

from variable_delay.src.argparse.help_formatter import BlankLinesHelpFormatter
from variable_delay.src.plot.plotter_args import *
from variable_delay.src.plot.per_flow_plot import PerFlowPlot
from variable_delay.src.plot.total_plot import TotalPlot
from variable_delay.src.plot.per_subset_plot import PerSubsetPlot, PlotTypeError
from variable_delay.src.plot.plotter import Plotter, MetadataError, DataError, StatsWriterError
from variable_delay.src.plot.plot_utils import is_color, array_to_color_cycle, color_cycle_to_array

WORKING_DIR          = os.path.dirname(os.path.realpath(__file__))
DEFAULT_IN_DIR_NAME  = os.path.join('graphs', 'data')
DEFAULT_IN_DIR_PATH  = os.path.join(WORKING_DIR, DEFAULT_IN_DIR_NAME)
DEFAULT_OUT_DIR_NAME = 'graphs'
DEFAULT_OUT_DIR_PATH = os.path.join(WORKING_DIR, DEFAULT_OUT_DIR_NAME)
EXIT_SUCCESS         = 0
EXIT_FAILURE         = 1
SUCCESS_MESSAGE      = "SUCCESS"
FAILURE_MESSAGE      = "FAILURE"


#
# Function processes argument specifying the color of Jain's Index curve to plot.
# param [in] jainsIndexColorArg - argument specifying the color of Jain's Index curve
# param [in] colorCycle         - color cycle of curves for other graphs
# returns the processed color of Jain's Index curve
#
def process_jains_color_arg(jainsIndexColorArg, colorCycle):
    jainsIndexColor = None

    if jainsIndexColorArg is None:
        if colorCycle is not None:
            jainsIndexColor = color_cycle_to_array(colorCycle)[0]
    else:
        jainsIndexColor = jainsIndexColorArg

        if is_color(jainsIndexColor) is False:
            sys.exit("Color in -j/--jains-index-color is not recognized by matplotlib: {}".
                     format(jainsIndexColor))

    return jainsIndexColor


#
# Function processes argument specifying the colors of the curves to plot.
# param [in] colorsArg - colors argument
# returns the color cycle of the curves to plot
#
def process_colors_argument(colorsArg):
    colorCycle = None

    if colorsArg is not None:
        colors = colorsArg.split()

        if len(colors) == 0:
            sys.exit("There must be colors in -c/--colors")

        for color in colors:
            if is_color(color) is False:
                sys.exit("Color in -c/--colors is not recognized by matplotlib: {}".format(color))

        colorCycle = array_to_color_cycle(colors)

    return colorCycle


#
# Function processes arguments specifying the required type of the plots/stats to make.
# param [in] perFlowArg   - per-flow type boolean argument
# param [in] totalArg     - total type boolean argument
# param [in] perSubsetArg - per-subset type string argument
# throws PlotTypeError
# returns the type of plots/stats to make
#
def process_type_arguments(perFlowArg, totalArg, perSubsetArg):
    if perFlowArg is False and totalArg is False and perSubsetArg is None:
        sys.exit('One of the flags -f, -t, -s should be chosen')

    if perFlowArg is True and totalArg     is True     or \
       perFlowArg is True and perSubsetArg is not None or \
       totalArg   is True and perSubsetArg is not None:
        sys.exit('Flags -f, -t, -s are mutually exclusive')

    if perFlowArg is True:
        return PerFlowPlot()

    if totalArg is True:
        return TotalPlot()

    if perSubsetArg is not None:
        return PerSubsetPlot(perSubsetArg.split())


#
# Function adds arguments to argparse argument parser.
# param [in, out] parser - argparse argument parser
#
def add_arguments(parser):
    parser.add_argument('-d', '--dir', default=DEFAULT_IN_DIR_PATH,
    help='Folder with input data-files, default is "%s"' % DEFAULT_IN_DIR_NAME)

    parser.add_argument('-o', '--output-dir', default=DEFAULT_OUT_DIR_PATH,
    help='Folder with output graphs and stats, default is "%s"' % DEFAULT_OUT_DIR_NAME)

    parser.add_argument('-f', '--per-flow', action='store_true',
    help='Graphs and stats are generated per flow, i.e. each graph has a separate curve per flow')

    parser.add_argument('-t', '--total', action='store_true',
    help='Total graphs and stats are generated for all flows altogether, '
         'i.e. each graph has only one curve')

    parser.add_argument('-s', '--per-subset', metavar='"FIELD1 FIELD2..."',
    help='Graphs and stats are generated per subset, i.e. each graph has one curve per subset. '
         'Flows are in one subset if they have the same values of the chosen layout field(s). '
         'E.g. for -s "scheme direction", each graph will have one curve per subset of flows '
         'having both the same scheme name and direction. Currently allowed layout fields: {}.'
         .format(PerSubsetPlot.ALLOWED_FIELDS))

    parser.add_argument('-i', '--interval', default=0.5, type=float, metavar='SEC',
    help='Interval per which average graphs are computed in seconds, default is 0.5')

    parser.add_argument('-c', '--colors', metavar='"COLOR1 COLOR2..."',
    help='Color cycle for curves with colors specified in any format recognized by matplotlib')

    parser.add_argument('-j', '--jains-index-color', metavar='COLOR',
    help='Color for Jain\'s index curve, if not specified the first color in -c/--colors is used')


#
# Function validates and adjusts arguments parsed by argparse parser.
# param [in] args - arguments parsed by argparse parser
# returns processed arguments
#
def process_arguments(args):
    output = { }

    output[SLOT_SEC] = args.interval

    if output[SLOT_SEC] <= 0.0:
        sys.exit('Interval should be positive')

    output[IN_DIR] = os.path.realpath(os.path.expanduser(args.dir))

    if not os.path.exists(output[IN_DIR]):
        sys.exit('Directory %s does not exist' % output[IN_DIR])

    output[OUT_DIR] = os.path.realpath(os.path.expanduser(args.output_dir))

    if not os.path.exists(output[OUT_DIR]):
        os.makedirs(output[OUT_DIR])

    output[PLOT_TYPE]         = process_type_arguments (args.per_flow, args.total, args.per_subset)

    output[COLOR_CYCLE]       = process_colors_argument(args.colors)

    output[JAINS_INDEX_COLOR] = process_jains_color_arg(args.jains_index_color, output[COLOR_CYCLE])

    return output


#
# Function processes input arguments of the script.
# returns list of input arguments of the script
#
def parse_arguments():
    parser = argparse.ArgumentParser(formatter_class=BlankLinesHelpFormatter, description=
    'The script makes graphs and stats over data extracted from pcap-files. Possible types of '
    'graphs and stats: per-flow (-f), total (-t), per-subset (-s). For any type chosen, the '
    'following graphs and stats are generated: average throughput, average Jain\'s index, average '
    'one-way delay, per-packet one-way delay. The average graphs are averaged per chosen time '
    'interval (-i). Average Jain\'s index graph always contains one curve, as it is computed over '
    'the curves present in the corresponding average throughput graph.')

    add_arguments(parser)

    args = parser.parse_args()

    return args


#
# Entry function
#
if __name__ == '__main__':
    exitCode = EXIT_SUCCESS
    args     = parse_arguments()

    try:
        args = process_arguments(args)

        Plotter(args).generate()

    except PlotTypeError as error:
        print("Diving flows into subsets ERROR:\n%s" % error)
    except MetadataError as error:
        print("Metadata ERROR:\n%s" % error)
    except DataError as error:
        print("Input data ERROR:\n%s" % error)
    except StatsWriterError as error:
        print("Writing statistics ERROR:\n%s" % error)
    except KeyboardInterrupt:
        print("KeyboardInterrupt was caught")
        exitCode = EXIT_FAILURE

    exitMessage = SUCCESS_MESSAGE if exitCode == EXIT_SUCCESS else FAILURE_MESSAGE
    print(exitMessage)

    sys.exit(exitCode)
