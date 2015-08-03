#!/usr/bin/env python

import sys
import os
import argparse
from subprocess import Popen, PIPE, call


def main(argv):
    
    parser = argparse.ArgumentParser(description='A command line way to edit video and audio metadata.')
    parser.add_argument('-f', '--file', action="store", dest="file", help='File to process')
    parser.add_argument('-t', '--title', action="store", dest="title", help='Title to apply')
    parser.add_argument('-d', '--description', action="store", dest="description", help='Description to apply')
    parser.add_argument('-ro', '--read_only', action="store_true", dest="read_only", help='Only print metadata, do not write')

    arguments = parser.parse_args()
    
    metadata_feed = dict()
    metadata_feed['title'] = arguments.title
    metadata_feed['description'] = arguments.description

    #print("command line: " + ', '.join(argv))
    if arguments.file:
        local_file = arguments.file
    else:
        print("no file given")
        return 1
    
    # read the file for any existing metadata
    #print("Calling Read Metadata")
    metadata_file = read_metadata(local_file)
    if metadata_file:
        for key in sorted(iter(metadata_file)):
            print("KEY: " + key + "=" + metadata_file[key])
            
        #print("Calling Write Metadata")
        if not arguments.read_only:
            print("Writing Metadata")
            metadata_write = write_metadata(local_file, metadata_feed, metadata_file)
    return 0

# read metadata from an audio or video file.  Assumes that it can call ffmpg in the path.  This dependency should be fixed.
# I've only tested with mp4 video files and mp3 audio files.  
def read_metadata(local_file):
    metadata = metadata_feed = dict()
    print("\nReading file: " + local_file)
    if not os.path.exists(local_file):
        print("File not found for metadata update")
        return 1
        
    cmd_line = ['ffmpeg', '-loglevel', 'quiet', '-i', local_file, '-f', 'ffmetadata', '-']

    try:
        process = Popen(cmd_line, stdout=PIPE, stderr=PIPE) # I'm not sure if I want to do anything with stderr yet
        stdout, stderr = process.communicate()
    except OSError as e:
        print >>sys.stderr, "FFMPEG Failed, aborting metadata updates:", e
        return 0

    for line in stdout.splitlines():
        line.rstrip()
        tokens = line.partition('=')
        if tokens[2]:
            #print("DATA: " + tokens[0] + " = " + tokens[2])
            if tokens[0] == 'title':
                metadata['TITLE_MATCH'] = tokens[2]
            elif tokens[0] == 'description' or tokens[0] == 'TDES':
                metadata['DESCRIPTION_MATCH'] = tokens[2]
            #elif tokens[0] == 'album':
            #    metadata['ALBUM_MATCH'] = tokens[2]
            #elif tokens[0] == 'minor_version':
            #    metadata['EPISODE_MATCH'] = tokens[2]

            metadata[tokens[0]] = tokens[2]
        #else:
        #    print("Not valid metadata: ", line)
    return(metadata)


# write metadata to an audio or video file.  Assumes that it can call ffmpg in the path.  This dependency should be fixed.
def write_metadata(local_file, metadata_feed, metadata_file):
    update_needed = 0
    cmd_line = ['ffmpeg', '-y', '-loglevel', 'quiet', '-i', local_file]
    tmp_file = "TMP_" + local_file  # note, for ffmpeg this needs to be the same extention

    # Which metadata do we have?
    if not 'TITLE_MATCH' in metadata_file:
        print("Adding Title: " + metadata_feed['title'])
        update_needed = 1
        cmd_line.extend(['-metadata', "title=" + metadata_feed['title']])
    else:
        print("Title already exists")
        
    if not 'DESCRIPTION_MATCH' in metadata_file:
        print("Adding Description: " + metadata_feed['description'])
        update_needed = 1
        cmd_line.extend(['-metadata', "description=" + metadata_feed['description']])
    else:
        print("Description already exists")

    if update_needed:
        print("Updating Metadata on " + local_file)
        
        cmd_line_mapping = ['-map', '0', '-codec', 'copy']
        cmd_line_end = [tmp_file]
        
        print("Command line: " + ' '.join(cmd_line + cmd_line_mapping + cmd_line_end))
        try:
            rtn = call(cmd_line + cmd_line_mapping + cmd_line_end)
            if rtn == 0:
                os.rename(tmp_file, local_file)
            else:
                # I have some podcasts that seem to have extra streams in them. I found this on Apple Byte podcast which has RTP hit streams.
                #print >>sys.stderr, "Child returned", rtn
                print("Trying to copy just one stream of audio and video")
                cmd_line_mapping = ['-codec', 'copy']
                rtn = call(cmd_line + cmd_line_mapping + cmd_line_end)
                if rtn != 0:
                    print("Copy Failed")
                    if os.path.exists(tmp_file):
                        os.remove(tmp_file)
                    return rtn
                else:
                   os.rename(tmp_file, local_file)
        except OSError as e:
            print >>sys.stderr, "Execution failed:", e
            return 0
    else:
        print("File already has title and description, no need to update the file")
    return 1


if __name__ == "__main__":
    main(sys.argv[1:])

