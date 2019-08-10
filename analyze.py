#!/usr/bin/env python

import sys
import os
import argparse

from variable_delay.src.argparse.help_formatter import BlankLinesHelpFormatter
from variable_delay.src.analyze.dump_analyzer import DumpAnalyzer
from variable_delay.src.analyze.dump_analyzer import MetadataError, AnalysisError, DataError

WORKING_DIR          = os.path.dirname(os.path.realpath(__file__))
DEFAULT_IN_DIR_NAME  = 'dumps'
DEFAULT_IN_DIR_PATH  = os.path.join(WORKING_DIR, DEFAULT_IN_DIR_NAME)
DEFAULT_OUT_DIR_NAME = os.path.join('graphs', 'data')
DEFAULT_OUT_DIR_PATH = os.path.join(WORKING_DIR, DEFAULT_OUT_DIR_NAME)
EXIT_SUCCESS         = 0
EXIT_FAILURE         = 1
SUCCESS_MESSAGE      = "SUCCESS"
FAILURE_MESSAGE      = "FAILURE"


#
# Function processes input arguments of the script
# returns list of input arguments of the script
#
def parse_arguments():
    parser = argparse.ArgumentParser(formatter_class=BlankLinesHelpFormatter, description=
    'The script extracts data from pcap-files captured during testing.')

    parser.add_argument('-d', '--dir', default=DEFAULT_IN_DIR_PATH,
                        help='folder with input pcap-files, default is "%s"' % DEFAULT_IN_DIR_NAME)

    parser.add_argument('-o', '--output-dir', default=DEFAULT_OUT_DIR_PATH,
                        help='folder with output files, default is "%s"' % DEFAULT_OUT_DIR_NAME)

    args = parser.parse_args()

    args.dir = os.path.realpath(os.path.expanduser(args.dir))

    if not os.path.exists(args.dir):
        sys.exit('Directory %s does not exist' % args.dir)

    args.output_dir = os.path.realpath(os.path.expanduser(args.output_dir))

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    return args


#
# Entry function
#
if __name__ == '__main__':
    args     = parse_arguments()
    exitCode = EXIT_SUCCESS

    try:
        DumpAnalyzer(args.dir, args.output_dir).extract_data()
    except MetadataError as error:
        print("Metadata ERROR:\n%s" % error)
        exitCode = EXIT_FAILURE
    except AnalysisError as error:
        print("Analysis of input dumps ERROR:\n%s" % error)
        exitCode = EXIT_FAILURE
    except DataError as error:
        print("Output data ERROR:\n%s" % error)
        exitCode = EXIT_FAILURE
    except KeyboardInterrupt:
        print("KeyboardInterrupt was caught")
        exitCode = EXIT_FAILURE

    exitMessage = SUCCESS_MESSAGE if exitCode == EXIT_SUCCESS else FAILURE_MESSAGE
    print(exitMessage)

    sys.exit(exitCode)
