#!/usr/bin/env python

import sys
import os
import argparse

from variable_delay.src.help_formatter import BlankLinesHelpFormatter
from variable_delay.src.per_flow_plot import PerFlowPlot
from variable_delay.src.total_plot import TotalPlot
from variable_delay.src.per_subset_plot import PerSubsetPlot, PlotTypeError
from variable_delay.src.plotter import Plotter, MetadataError, DataError

WORKING_DIR          = os.path.dirname(os.path.realpath(__file__))
DEFAULT_IN_DIR_NAME  = os.path.join('graphs', 'data')
DEFAULT_IN_DIR_PATH  = os.path.join(WORKING_DIR, DEFAULT_IN_DIR_NAME)
DEFAULT_OUT_DIR_NAME = 'graphs'
DEFAULT_OUT_DIR_PATH = os.path.join(WORKING_DIR, DEFAULT_OUT_DIR_NAME)
INTERVAL             = 'interval'
IN_DIR               = 'in-dir'
OUT_DIR              = 'out-dir'
TYPE                 = 'type'
EXIT_SUCCESS         = 0
EXIT_FAILURE         = 1
SUCCESS_MESSAGE      = "SUCCESS"
FAILURE_MESSAGE      = "FAILURE"


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


#
# Function validates and adjusts arguments parsed by argparse parser.
# param [in] args - arguments parsed by argparse parser
# returns processed arguments
#
def process_arguments(args):
    output = { }

    output[INTERVAL] = args.interval

    if output[INTERVAL] <= 0.0:
        sys.exit('Interval should be positive')

    output[IN_DIR] = os.path.realpath(os.path.expanduser(args.dir))

    if not os.path.exists(output[IN_DIR]):
        sys.exit('Directory %s does not exist' % output[IN_DIR])

    output[OUT_DIR] = os.path.realpath(os.path.expanduser(args.output_dir))

    if not os.path.exists(output[OUT_DIR]):
        os.makedirs(output[OUT_DIR])

    output[TYPE] = process_type_arguments(args.per_flow, args.total, args.per_subset)

    return output


#
# Function processes input arguments of the script.
# returns list of input arguments of the script
#
def parse_arguments():
    parser = argparse.ArgumentParser(formatter_class=BlankLinesHelpFormatter, description=
    'The script makes graphs and stats over data extracted from pcap-files. Possible types of '
    'graphs and stats: per-flow (-f), total (-t), per-subset (-s). For any type chosen, the '
    'following graphs and stats are generated: average throughput, average Jain index, average '
    'one-way delay, per-packet one-way delay. The average graphs are averaged per chosen time '
    'interval (-i).')

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

        Plotter(args[IN_DIR], args[OUT_DIR], args[INTERVAL], args[TYPE]).generate()

    except PlotTypeError as error:
        print("Diving flows into subsets ERROR:\n%s" % error)
    except MetadataError as error:
        print("Metadata ERROR:\n%s" % error)
    except DataError as error:
        print("Input data ERROR:\n%s" % error)
    except KeyboardInterrupt:
        print("KeyboardInterrupt was caught")
        exitCode = EXIT_FAILURE

    exitMessage = SUCCESS_MESSAGE if exitCode == EXIT_SUCCESS else FAILURE_MESSAGE
    print(exitMessage)

    sys.exit(exitCode)
