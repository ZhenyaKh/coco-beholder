#!/usr/bin/env python

import os
import json

from variable_delay.src.layout.layout_fields import FLOWS, START
from variable_delay.src.processed_args import args_names
from variable_delay.src.metadata import metadata_fields

METADATA_NAME = 'metadata.json'


#
# Custom Exception class for errors connected to processing of metadata containing testing's input
#
class MetadataError(Exception):
    pass


#
# Function generates metadata using processed arguments and parsed layout.
# param [in] processedArgs - processed arguments
# param [in] parsedLayout  - parsed layout
# returns metadata
#
def compute_metadata(processedArgs, parsedLayout):
    metadata =\
    {
        metadata_fields.RATE          : processedArgs[args_names.RATE        ],
        metadata_fields.RUNTIME       : processedArgs[args_names.RUNTIME     ],
        metadata_fields.MAX_DELAY     : processedArgs[args_names.MAX_DELAY   ],
        metadata_fields.SEED          : processedArgs[args_names.SEED        ],
        metadata_fields.BUFFER        : processedArgs[args_names.BUFFER      ],
        metadata_fields.FIRST_QUEUE   : processedArgs[args_names.FIRST_QUEUE ],
        metadata_fields.SECOND_QUEUE  : processedArgs[args_names.SECOND_QUEUE],
        metadata_fields.BASE          : processedArgs[args_names.BASE        ],
        metadata_fields.DELTA         : processedArgs[args_names.DELTA       ],
        metadata_fields.STEP          : processedArgs[args_names.STEP        ],
        metadata_fields.JITTER        : processedArgs[args_names.JITTER      ],
        metadata_fields.SORTED_LAYOUT : sorted(parsedLayout, key=lambda flow: flow[START]),
        metadata_fields.ALL_FLOWS     : sum(entry[FLOWS] for entry in parsedLayout)
    }

    return metadata


#
# Function saves metadata to json-file.
# param [in] directoryPath - full path of the output directory
# param [in] metadata      - dictionary with metadata
# throws MetadataError
#
def save_metadata(directoryPath, metadata):
    metadataPath = os.path.join(directoryPath, METADATA_NAME)

    try:
        with open(metadataPath, 'w') as metadataFile:
            json.dump(metadata, metadataFile, sort_keys=True, indent=4, separators=(',', ': '))
    except Exception as error:
        raise MetadataError('Failed to save meta: %s' % error)


#
# Function loads metadata of the testing.
# param [in] directoryPath - full path of the directory containing metadata file
# throws MetadataError
# returns dictionary with metadata
#
def load_metadata(directoryPath):
    metadataPath = os.path.join(directoryPath, METADATA_NAME)

    try:
        with open(metadataPath) as metadataFile:
            metadata     = json.load(metadataFile)
            layout       = metadata[metadata_fields.SORTED_LAYOUT]
            sortedLayout = sorted(layout, key=lambda flow: flow[START])
            layoutFlows  = sum(entry[FLOWS] for entry in layout)

            assert sortedLayout == layout
            assert layoutFlows  == metadata[metadata_fields.ALL_FLOWS]

    except IOError as error:
        raise MetadataError('Failed to open meta: %s' % error)
    except ValueError as error:
        raise MetadataError('Failed to load meta: %s' % error)

    return metadata
