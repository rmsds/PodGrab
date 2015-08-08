#!/usr/bin/env python

# PodGrab - A Python command line audio/video podcast downloader for RSS XML feeds.
# Supported RSS item file types: MP3, M4V, OGG, FLV, MP4, MPG/MPEG, WMA, WMV, WEBM
# Version: 1.1.2 - 06/10/2011
# Jonathan Baker
# jon@the-node.org (http://the-node.org)

# Version: 1.1.3 -
#   - added small changes to write M3U file of podcasts downloaded today
# Werner Avenant
# werner.avenant@gmail.com (http://www.collectiveminds.co.za)

# Version: 1.1.4 - 07/31/2015
#   - added command line switches for db location, download location, plex configuration, M3U creation
#   - changed mkdir to mkdirs
# Version 1.1.5 - 8/2/2015
#   - added option to populate missing metadata in the mp3/mp4 file from the information in the feed.
# David Smith

# Do with this code what you will, it's "open source". As a courtesy,
# I would appreciate credit if you base your code on mine. If you find
# a bug or think the code sucks balls, please let me know :-)

# Outstanding issues:-
# - Video podcasts which which are not direct URLs and are modified by PodGrab
#   in order to be grabbed won't display their size as the filenames haven't
#   been stripped of their garbage URL info yet. It'll say 0 bytes, but don't
#   worry, they've downloaded.


from __future__ import unicode_literals
import os
import sys
import argparse
import urllib2
import xml.dom.minidom
import datetime
from time import gmtime, strftime, strptime, mktime
import sqlite3
import shutil
import smtplib
from email.mime.text import MIMEText
import platform
import traceback
import unicodedata
from subprocess import Popen, PIPE, call


MODE_NONE = 70
MODE_SUBSCRIBE = 71
MODE_DOWNLOAD = 72
MODE_UNSUBSCRIBE = 73
MODE_LIST = 74
MODE_UPDATE = 75
MODE_MAIL_ADD = 76
MODE_MAIL_DELETE = 77
MODE_MAIL_LIST = 78
MODE_EXPORT = 79
MODE_IMPORT = 80

NUM_MAX_DOWNLOADS = 4
PLEX_NAMING = 0
CREATE_M3U = 0
UPDATE_METADATA = 0

DOWNLOAD_DIRECTORY = "podcasts"
#DOWNLOAD_DIRECTORY = os.path.realpath("/home/hrehfeld/host/d/download/podcasts_podgrab")

# Added 2011-10-06 Werner Avenant - added current_dictory here so it can be global
current_directory = ''
m3u_file = ''

total_item = 0
total_size = 0
has_error = 0


def main(argv):
    mode = MODE_NONE
    has_error = 0
    num_podcasts = 0
    error_string = ""
    feed_url = ""
    feed_name = ""
    mail_address = ""
    message = ""
    mail = ""
    # Added 2011-10-06 Werner Avenant
    global current_directory
    global m3u_file
    now = datetime.datetime.now();
    m3u_file = str(now)[:10] + '.m3u'
    current_directory = os.path.realpath(os.path.dirname(sys.argv[0]))
    global db_name
    global db_path
    db_name = "PodGrab.db"
    db_path=current_directory

    global UPDATE_METADATA
    global DOWNLOAD_DIRECTORY
    global NUM_MAX_DOWNLOADS
    global PLEX_NAMING
    global CREATE_M3U
    global total_items
    global total_size
    total_items = 0
    total_size = 0
    data = ""


    parser = argparse.ArgumentParser(description='A command line Podcast downloader for RSS XML feeds')
    parser.add_argument('-s', '--subscribe', action="store", dest="sub_feed_url", help='Subscribe to the following XML feed and download latest podcast')
    parser.add_argument('-d', '--download', action="store", dest="dl_feed_url", help='Bulk download all podcasts in the following XML feed or file')
    parser.add_argument('-un', '--unsubscribe', action="store", dest="unsub_url", help='Unsubscribe from the following Podcast feed')
    parser.add_argument('-ma', '--mail-add', action="store", dest="mail_address_add", help='Add a mail address to mail subscription updates to')
    parser.add_argument('-md', '--mail-delete', action="store", dest="mail_address_delete", help='Delete a mail address')

    parser.add_argument('-l', '--list', action="store_const", const="ALL", dest="list_subs", help='Lists current Podcast subscriptions')
    parser.add_argument('-u', '--update', action="store_const", const="UPDATE", dest="update_subs", help='Updates all current Podcast subscriptions')
    parser.add_argument('-ml', '--mail-list', action="store_const", const="MAIL", dest="list_mail", help='Lists all current mail addresses')

    parser.add_argument('-io', '--import', action="store", dest="opml_import", help='Import subscriptions from OPML file')
    parser.add_argument('-eo', '--export', action="store_const", const="OPML_EXPORT", dest="opml_export", help='Export subscriptions to OPML file')
    
    parser.add_argument('-pn', '--plex-naming', action="store_true", dest="plex_naming", help='Name files with Season=Year and Epsiode=Month+Day')
    parser.add_argument('-max', '--max-downloads', action="store", dest="max_downloads", help='Max number of podcasts to download')
    parser.add_argument('-dir', '--download-directory', action="store", dest="download_directory", help='Directory to store podcasts in')
    parser.add_argument('-db', '--db_path', action="store", dest="db_path", help='Location of the PodGrab.db file')
    parser.add_argument('-m3u', '--create-m3u', action="store_true", dest="create_m3u", help='Create m3u files for playlists')
    parser.add_argument('-um', '--update_metadata', action="store_true", dest="update_metadata", help='Use ffmpeg to update metadata with the title and description from the feed')


    arguments = parser.parse_args()

    if arguments.update_metadata:
        print("Metadata will be updated")
        UPDATE_METADATA = 1
    else:
        print("Metadata will be left alone")

    if arguments.download_directory:
        DOWNLOAD_DIRECTORY = arguments.download_directory
    
    if arguments.db_path:
        db_path = arguments.db_path
    
    if arguments.max_downloads:
        NUM_MAX_DOWNLOADS = int(arguments.max_downloads)
    print("Max items per podcast is " + str(NUM_MAX_DOWNLOADS))

    if arguments.plex_naming:
        print("PLEX naming is on")
        PLEX_NAMING = 1
    else:
        print("PLEX naming is off")

    if arguments.create_m3u:
        print("M3U files will be created")
        CREATE_M3U = 1
    else:
        print("M3U files will not created")

    if arguments.sub_feed_url:
        feed_url = arguments.sub_feed_url
        data = open_datasource(feed_url)
        if not data:
            error_string = "Not a valid XML file or URL feed!"
            has_error = 1
            exit_clean(error_string, 1)
            
        else:
            print("XML data source opened\n")
            mode = MODE_SUBSCRIBE

    elif arguments.dl_feed_url:
        feed_url = arguments.dl_feed_url
        data = open_datasource(feed_url)
        if not data:
            error_string = "Not a valid XML file or URL feed!"
            has_error = 1
            exit_clean(error_string, 1)
        else:
            print("XML data source opened\n")
            mode = MODE_DOWNLOAD

    elif arguments.unsub_url:
        feed_url = arguments.unsub_url
        mode = MODE_UNSUBSCRIBE

    elif arguments.list_subs:
        mode = MODE_LIST

    elif arguments.update_subs:
        mode = MODE_UPDATE

    elif arguments.mail_address_add:
        mail_address = arguments.mail_address_add
        mode = MODE_MAIL_ADD

    elif arguments.mail_address_delete:
        mail_address = arguments.mail_address_delete
        mode = MODE_MAIL_DELETE

    elif arguments.list_mail:
        mode = MODE_MAIL_LIST

    elif arguments.opml_import:
        import_file_name = arguments.opml_import
        mode = MODE_IMPORT

    elif arguments.opml_export:
        mode = MODE_EXPORT

    else:
        error_string = "No Arguments supplied - for usage run 'PodGrab.py -h'"
        has_error = 1
        exit_clean(error_string, 1)

    print("Default encoding: " + sys.getdefaultencoding())
    todays_date = strftime("%a, %d %b %Y %H:%M:%S", gmtime())
    print("Current Directory: " + current_directory)

# Database Check/Create
    if does_database_exist(current_directory):
        connection = connect_database(current_directory)
        if not connection:
            error_string = "Could not connect to PodGrab database file!"
            has_error = 1
            exit_clean(error_string, 1)
        else:
            cursor = connection.cursor()
    else:
        print("PodGrab database missing. Creating...")
        connection = connect_database(current_directory)
        if not connection:
            error_string = "Could not create PodGrab database file!"
            has_error = 1
            exit_clean(error_string, 1)
        else:
            print("PodGrab database created")
            cursor = connection.cursor()
            setup_database(cursor, connection)
            print("Database setup complete")


# Download Directory
    if not os.path.exists(DOWNLOAD_DIRECTORY):
        print("Podcast download directory is missing. Creating...")
        try:
            os.makedirs(DOWNLOAD_DIRECTORY)
            print("Download directory '" + DOWNLOAD_DIRECTORY + "' created")
        except OSError:
            error_string = "Could not create podcast download sub-directory!"
            has_error = 1
            exit_clean(error_string, 1)
    else:
        print("Download directory exists: '" + DOWNLOAD_DIRECTORY + "'" )
    if not has_error:
        if mode == MODE_UNSUBSCRIBE:
            feed_name = get_name_from_feed(cursor, connection, feed_url)
            if feed_name == "None":
                print("Feed does not exist in the database! Skipping...")
            else:
                feed_name = clean_string(feed_name)
                channel_directory = DOWNLOAD_DIRECTORY + os.sep + feed_name
                print("Deleting '" + channel_directory + "'...")
                delete_subscription(cursor, connection, feed_url)
                try :
                    shutil.rmtree(channel_directory)
                except OSError:
                    print("Subscription directory has not been found - it might have been manually deleted" )
                print("Subscription '" + feed_name + "' removed")
        elif mode == MODE_LIST:
            print("Listing current podcast subscriptions...\n")
            list_subscriptions(cursor, connection)
        elif mode == MODE_UPDATE:
            print("Updating all podcast subscriptions...")
            subs = get_subscriptions(cursor, connection)
            for sub in subs:
                feed_name = sub[0]
                feed_url = sub[1]
                print("Feed for subscription: '" + feed_name + "' from '" + feed_url + "' is updating...")
                data = open_datasource(feed_url)
                if not data:
                    print("'" + feed_url + "' for '" + feed_name + "' is not a valid feed URL!")
                else:
                    message = iterate_feed(data, mode, DOWNLOAD_DIRECTORY, todays_date, cursor, connection, feed_url)
                    print(message)
                    mail += message
            mail = mail + "\n\n" + str(total_items) + " podcasts totalling " + str(total_size) + " bytes have been downloaded."
            if has_mail_users(cursor, connection):
                print("Have e-mail address(es) - attempting e-mail...")
                mail_updates(cursor, connection, mail, str(total_items))
        elif mode == MODE_DOWNLOAD or mode == MODE_SUBSCRIBE:
            print(iterate_feed(data, mode, DOWNLOAD_DIRECTORY, todays_date, cursor, connection, feed_url))
        elif mode == MODE_MAIL_ADD:
            add_mail_user(cursor, connection, mail_address)
            print("E-Mail address: " + mail_address + " has been added")
        elif mode == MODE_MAIL_DELETE:
            delete_mail_user(cursor, connection, mail_address)
            print("E-Mail address: " + mailAddress + " has been deleted")
        elif mode == MODE_MAIL_LIST:
            list_mail_addresses(cursor, connection)
        elif mode == MODE_EXPORT:
            export_opml_file(cursor, connection, current_directory)
        elif mode == MODE_IMPORT:
            import_opml_file(cursor, connection, current_directory, DOWNLOAD_DIRECTORY, import_file_name)
    else:
        #print("Sorry, there was some sort of error: '" + error_string + "'\nExiting...\n")
        #if connection:
        #    connection.close()
        exit_clean(error_string, 1)
#
# End of main()
#

def exit_clean(error_string, error_code):
    print("Sorry, there was some sort of error: '" + error_string + "'\nExiting...\n")
    #if connection:
    #    connection.close()
    sys.exit(error_code)

def open_datasource(xml_url):
    try:
        response = urllib2.urlopen(xml_url)
    except ValueError:
        try:
            response = open(xml_url,'r')
        except ValueError:
            print("ERROR - Invalid feed!")
            response = False
    except urllib2.URLError:
        print("ERROR - Connection problems. Please try again later")
        response = False
    except httplib.IncompleteRead:
        print("ERROR - Incomplete data read. Please try again later")
        response = False
    if response != False:
        return response.read()
    else:
        return response

def export_opml_file(cur, conn, cur_dir):
    item_count = 0
    feed_name = ""
    feed_url = ""
    last_ep = ""
    now = datetime.datetime.now()
    file_name = cur_dir + os.sep + "podgrab_subscriptions-" + str(now.year) + "-" + str(now.month) + "-" + str(now.day) + ".opml"
    subs = get_subscriptions(cur, conn)
    file_handle = open(file_name,"w")
    print("Exporting RSS subscriptions database to: '" + file_name + "' OPML file...please wait.\n")
    header = "<opml version=\"2.0\">\n<head>\n\t<title>PodGrab Subscriptions</title>\n</head>\n<body>\n"
    file_handle.writelines(header)
    for sub in subs:
        feed_name = sub[0]
        feed_url = sub[1]
        last_ep = sub[2]
        file_handle.writelines("\t<outline title=\"" + feed_name + "\" text=\"" + feed_name + "\" type=\"rss\" xmlUrl=\"" + feed_url + "\" htmlUrl=\"" + feed_url + "\"/>\n")
        print("Exporting subscription '" + feed_name + "'...Done.\n")
        item_count = item_count + 1
    footer = "</body>\n</opml>"
    file_handle.writelines(footer)
    file_handle.close()
    print(str(item_count) + " item(s) exported to: '" + file_name + "'. COMPLETE")


def import_opml_file(cur, conn, cur_dir, download_dir, import_file):
    count = 0
    print("Importing OPML file '" + import_file + "'...")
    if import_file.startswith("/") or import_file.startswith(".."):
        data = open_datasource(import_file)
        if not data:
            print("ERROR = Could not open OPML file '" + import_file + "'")
    else:
        data = open_datasource(cur_dir + os.sep + import_file)
        if not data:
            print("ERROR - Could not open OPML file '" + cur_dir + os.sep + import_file + "'")
    if data:
        print("File opened...please wait")
        try:
            xml_data = xml.dom.minidom.parseString(data)
            items = xml_data.getElementsByTagName('outline')
            for item in items:
                item_feed = item.getAttribute('xmlUrl').encode('utf-8')
                item_name = item.getAttribute('title').encode('utf-8')
                item_name = clean_string(item_name)
                print("Subscription Title: " + item_name)
                print("Subscription Feed: " + item_feed)
                item_directory = download_dir + os.sep + item_name

                if not os.path.exists(item_directory):
                    os.makedirs(item_directory)
                if not does_sub_exist(cur, conn, item_feed):
                    insert_subscription(cur, conn, item_name, item_feed)
                    count = count + 1
                else:
                    print("This subscription is already present in the database. Skipping...")
                print("\n")
            print("\nA total of " + str(count) + " subscriptions have been added from OPML file: '" + import_file + "'")
            print("These will be updated on the next update run.\n")
        except xml.parsers.expat.ExpatError:
            print("ERROR - Malformed XML syntax in feed. Skipping...")


def iterate_feed(data, mode, download_dir, today, cur, conn, feed):
    print("Iterating feed...")
    message = ""
    try:
        xml_data = xml.dom.minidom.parseString(data)
        for channel in xml_data.getElementsByTagName('channel'):
            channel_title = channel.getElementsByTagName('title')[0].firstChild.data
            channel_link = channel.getElementsByTagName('link')[0].firstChild.data
            print("Channel Title: === " + channel_title + " ===")
            print("Channel Link: " + channel_link)
            channel_title = clean_string(channel_title)

            channel_directory = download_dir + os.sep + channel_title
            if not os.path.exists(channel_directory):
                os.makedirs(channel_directory)
            print("Current Date: " + today)
            if mode == MODE_DOWNLOAD:
                print("Bulk download. Processing...")
                # 2011-10-06 Replaced channel_directory with channel_title - needed for m3u file later
                num_podcasts = iterate_channel(channel, today, mode, cur, conn, feed, channel_title)
                print("\n" + num_podcasts + "have been downloaded")
            elif mode == MODE_SUBSCRIBE:
                print("Feed to subscribe to: " + feed + ".\nChecking for database duplicate...")
                if not does_sub_exist(cur, conn, feed):
                    print("Subscribe.\nProcessing...")
                    # 2011-10-06 Replaced channel_directory with channel_title - needed for m3u file later
                    num_podcasts = iterate_channel(channel, today, mode, cur, conn, feed, channel_title)

                    print("\n" + num_podcasts + "have been downloaded from your subscription")
                else:
                    print("Subscription already exists! Skipping...")
            elif mode == MODE_UPDATE:
                print("Updating RSS feeds. Processing...")
                num_podcasts = iterate_channel(channel, today, mode, cur, conn, feed, channel_title)
                message += str(num_podcasts) + " have been downloaded from your subscription: '" + channel_title + "'\n"
    except xml.parsers.expat.ExpatError:
        print("ERROR - Malformed XML syntax in feed. Skipping...")
        message += "0 podcasts have been downloaded from this feed due to RSS syntax problems. Please try again later"
    except UnicodeEncodeError as e:
        print(e)
        print("ERROR - Unicode encoding error in string. Cannot convert to ASCII. Skipping...")
        message += "0 podcasts have been downloaded from this feed due to RSS syntax problems. Please try again later"
    return message


def clean_string(str):
    new_string = str
    if new_string.startswith("-"):
        new_string = new_string.lstrip("-")
    if new_string.endswith("-"):
        new_string = new_string.rstrip("-")
    new_string_final = ''
    for c in new_string:
        if c.isalnum() or c == "-" or c == "_" or c == "." or c.isspace():
            new_string_final = new_string_final + ''.join(c)
            new_string_final = new_string_final.replace(' ','_')
            new_string_final = new_string_final.replace('---','-')
            new_string_final = new_string_final.replace('--','-')
            new_string_final = new_string_final.strip()

    return new_string_final

# Change 2011-10-06 - Changed chan_loc to channel_title to help with relative path names
# in the m3u file
def write_podcast(item, channel_title, date, type, title, metadata_feed):
    (item_path, item_file_name) = os.path.split(item)
    plex_info = ""
    item_save_name = item_file_name
    
    # Added name and season to the saved file name based on the date released.  This is compatible with Plex TV inputs.
    if PLEX_NAMING:
        struct_time_item = datetime.datetime.strptime(fix_date(date), "%a, %d %b %Y %H:%M:%S")
        plex_info = channel_title + "." + struct_time_item.strftime("S%YE%m%d") + "."
        item_save_name = plex_info + title

    if len(item_save_name) > 50:
        item_save_name = item_save_name[:50]

    local_file = DOWNLOAD_DIRECTORY + os.sep + channel_title + os.sep + clean_string(item_save_name)

    local_file = fix_file_extention(type, local_file)

    # Check if file exists, but if the file size is zero (which happens when the user
    # presses Crtl-C during a download) - the the code should go ahead and download
    # as if the file didn't exist
    if os.path.exists(local_file) and os.path.getsize(local_file) != 0:
        return 'File Exists'
    else:
        print("\nDownloading " + item_file_name + " as \"" + clean_string(item_save_name) + "\"" + " which was published on " + date)
        try:
            req = urllib2.urlopen(item)
            CHUNK = 16 * 1024
            with open(local_file, 'wb') as fp:
              while True:
                chunk = req.read(CHUNK)
                if not chunk: break
                fp.write(chunk)

            item_file_name = os.path.basename(fp.name)
            print("Podcast: " + item + " downloaded to: " + local_file)

            # 2011-11-06 Append to m3u file
            if CREATE_M3U:
                print("Creating M3U file in " + DOWNLOAD_DIRECTORY + os.sep + m3u_file)
                output = open(DOWNLOAD_DIRECTORY + os.sep + m3u_file, 'a')
                output.write(DOWNLOAD_DIRECTORY + os.sep + channel_title + os.sep + item_file_name + "\n")
                output.close()

            # add missing metadata in the file to match metadata in the feed
            if UPDATE_METADATA:
                metadata_file = read_metadata(local_file)
                if metadata_file:
                    for key in sorted(iter(metadata_file)):
                        print("Existing Metadata: " + key + "=" + metadata_file[key])
                    metadata_write = write_metadata(local_file, metadata_feed, metadata_file)
            return 'Successful Write'
        except urllib2.URLError as e:
            print("ERROR - Could not write item to file: " + e)
            return 'Write Error'


# Fix any odd file endings
def fix_file_extention(type, local_file):
    if type == "video/quicktime" or type == "audio/mp4" or type == "video/mp4":
        if not local_file.endswith(".mp4"):
            local_file = local_file + ".mp4"
    elif type == "video/mpeg":
        if not local_file.endswith(".mpg"):
            local_file = local_file + ".mpg"
    elif type == "video/x-flv":
        if not local_file.endswith(".flv"):
            local_file = local_file + ".flv"
    elif type == "video/x-ms-wmv":
        if not local_file.endswith(".wmv"):
            local_file = local_file + ".wmv"
    elif type == "video/webm" or type == "audio/webm":
        if not local_file.endswith(".webm"):
            local_file = local_file + ".webm"
    elif type == "audio/mpeg":
        if not local_file.endswith(".mp3"):
            local_file = local_file + ".mp3"
    elif type == "audio/ogg" or type == "video/ogg" or type == "audio/vorbis":
        if not local_file.endswith(".ogg"):
            local_file = local_file + ".ogg"
    elif type == "audio/x-ms-wma" or type == "audio/x-ms-wax":
        if not local_file.endswith(".wma"):
            local_file = local_file + ".wma"
    return(local_file)


# read metadata from an audio or video file.  Assumes that it can call ffmpg in the path.  This dependency should be fixed.
# I've only tested with mp4 video files and mp3 audio files.  
def read_metadata(local_file):
    metadata = metadata_feed = dict()
    #print("\nReading file: " + local_file)
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
    (item_path, item_file_name) = os.path.split(local_file)
    tmp_file = item_path + os.sep + "TMP_" + item_file_name  # note, for ffmpeg this needs to be the same extention

    # Which metadata do we have?
    if not 'TITLE_MATCH' in metadata_file:
        #print("Adding Title: " + metadata_feed['title'])
        update_needed = 1
        cmd_line.extend(['-metadata', "title=" + metadata_feed['title']])
        
    if not 'DESCRIPTION_MATCH' in metadata_file:
        #print("Adding Description: " + metadata_feed['description'])
        update_needed = 1
        cmd_line.extend(['-metadata', "description=" + metadata_feed['description']])

    if update_needed:
        print("Updating Metadata on " + local_file)
        
        cmd_line_mapping = ['-map', '0', '-codec', 'copy']
        cmd_line_end = [tmp_file]
        
        try:
            rtn = call(cmd_line + cmd_line_mapping + cmd_line_end)
            if rtn == 0:
                os.rename(tmp_file, local_file)
            else:
                # I have some podcasts that seem to have extra streams in them. I found this on Apple Byte podcast which has RTP hit streams.
                #print >>sys.stderr, "Child returned", rtn
                print("Unknown streams found, Trying to copy just one stream of audio and video for metadata")
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
            return 1
    else:
        print("File already has embedded title and description, no need to update the file")
    return 0


def does_database_exist(curr_loc):
    if os.path.exists(db_path + os.sep + db_name):
        return 1
    else:
        return 0


def add_mail_user(cur, conn, address):
    row = (address,)
    cur.execute('INSERT INTO email(address) VALUES (?)', row)
    conn.commit()


def delete_mail_user(cur, conn, address):
    row = (address,)
    cur.execute('DELETE FROM email WHERE address = ?', row)
    conn.commit()


def get_mail_users(cur, conn):
    cur.execute('SELECT address FROM email')
    return cur.fetchall()


def list_mail_addresses(cur, conn):
    cur.execute('SELECT * from email')
    result = cur.fetchall()
    print("Listing mail addresses...")
    for address in result:
        print("Address:\t" + address[0])


def has_mail_users(cur, conn):
    cur.execute('SELECT COUNT(*) FROM email')
    if cur.fetchone() == "0":
        return 0
    else:
        return 1


def mail_updates(cur, conn, mess, num_updates):
    addresses = get_mail_users(cur, conn)
    for address in addresses:
        try:
            subject_line = "PodGrab Update"
            if int(num_updates) > 0:
                subject_line += " - NEW updates!"
            else:
                subject_line += " - nothing new..."
            mail('localhost', 'podgrab@' + platform.node(), address[0], subject_line, mess)
            print("Successfully sent podcast updates e-mail to: " + address[0])
        except smtplib.SMTPException:
            traceback.print_exc()
            print("Could not send podcast updates e-mail to: " + address[0])


def mail(server_url=None, sender='', to='', subject='', text=''):
    headers = "From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n" % (sender, to, subject)
    message = headers + text
    mail_server = smtplib.SMTP(server_url)
    mail_server.sendmail(sender, to, message)
    mail_server.quit()


def connect_database(curr_loc):
    #conn = sqlite3.connect(curr_loc + os.sep + "PodGrab.db")
    if not os.path.exists(db_path):
        try:
            print("Creating dir " + db_path)
            os.makedirs(db_path)
        except OSError:
            error_string = "Could not create podcast database directory!"
            return 0

    conn = sqlite3.connect(db_path + os.sep + db_name)
    return conn


def setup_database(cur, conn):
    cur.execute("CREATE TABLE subscriptions (channel text, feed text, last_ep text)")
    cur.execute("CREATE TABLE email (address text)")
    conn.commit()


def insert_subscription(cur, conn, chan, feed):
    chan.replace(' ', '-')
    chan.replace('---','-')
    row = (chan, feed, "Thu, 01 Jan 1970 00:00:00") # Added a correctly formatted date here so we can avoid an ugly "if date == null" in update_subscription later
    cur.execute('INSERT INTO subscriptions(channel, feed, last_ep) VALUES (?, ?, ?)', row)
    conn.commit()


def iterate_channel(chan, today, mode, cur, conn, feed, channel_title):
    global total_items
    global total_size
    num = 0
    saved = 0
    size = 0
    last_ep = "NULL"
    print("Iterating channel...")

    if does_sub_exist(cur, conn, feed):
        print("Podcast subscription exists")

    else:
        print("Podcast subscription is new - getting previous podcast")
        insert_subscription(cur, conn, chan.getElementsByTagName('title')[0].firstChild.data, feed)

    last_ep = get_last_subscription_downloaded(cur, conn, feed)

    ### NB NB - The logic here is that we get the "last_ep" before we enter the loop
    ### The result is that it allows the code to "catch up" on missed episodes because
    ### we never update the "last_ep" while inside the loop.

    for item in chan.getElementsByTagName('item'):
        try:
            item_title = item.getElementsByTagName('title')[0].firstChild.data
            item_desc = item.getElementsByTagName('description')[0].firstChild.data
            item_date = item.getElementsByTagName('pubDate')[0].firstChild.data
            item_file = item.getElementsByTagName('enclosure')[0].getAttribute('url')
            item_size = item.getElementsByTagName('enclosure')[0].getAttribute('length')
            item_type = item.getElementsByTagName('enclosure')[0].getAttribute('type')
            struct_time_today = strptime(today, "%a, %d %b %Y %H:%M:%S")

            #item_title = item_title.strip()
            #item_desc = item_desc.strip()
            metadata_feed = dict()
            metadata_feed['title'] = item_title
            metadata_feed['description'] = item_desc
            metadata_feed['date'] = item_date
            metadata_feed['file'] = item_file
            metadata_feed['size'] = item_size
            metadata_feed['type'] = item_type

            has_error = 0
            try:
                struct_time_item = strptime(fix_date(item_date), "%a, %d %b %Y %H:%M:%S")
            except TypeError:
                has_error = 1
            except ValueError:
                has_error = 1

            try:
                struct_last_ep = strptime(last_ep, "%a, %d %b %Y %H:%M:%S")
            except TypeError:
                has_error = 1
                print("This item has a badly formatted date. Cannot download!")
            except ValueError:
                has_error = 1
                print("This item has a badly formatted date. Cannot download!")

            if not has_error:
                if mktime(struct_time_item) > mktime(struct_last_ep) or mode == MODE_DOWNLOAD:
                    saved = write_podcast(item_file, channel_title, item_date, item_type, item_title, metadata_feed)

                    if saved == 'File Exists':
                        print("File Existed - updating local database's Last Episode")
                        update_subscription(cur, conn, feed, fix_date(item_date))

                    if saved == 'Successful Write':
                        print("\nTitle: " + item_title)
                        print("Description: " + item_desc)
                        print("Date:  " + item_date)
                        print("File:  " + item_file)
                        print("Size:  " + item_size + " bytes")
                        print("Type:  " + item_type)
                        update_subscription(cur, conn, feed, fix_date(item_date))
                        num += 1
                        if len(item_size):
                            size = size + int(item_size)
                        total_size += size
                        total_items += 1

                    if (mode == MODE_SUBSCRIBE): # In subscribe mode we only want 1 this loop to execute once
                        break;

                    if (num >= NUM_MAX_DOWNLOADS):
                        print("Maximum session download of " + str(NUM_MAX_DOWNLOADS) + " podcasts has been reached. Exiting.")
                        break
                else:
                    print("According to database we already have the episode dated " + item_date)
                    break

        except IndexError as e:
            #traceback.print_exc()
            print("This RSS item has no downloadable URL link for the podcast for '" + item_title  + "'. Skipping...")

    return(str(num) + " podcast(s) totalling " + str(size) + " byte(s)")


def fix_date(date):
    new_date = ""
    split_array = date.split(' ')
    for i in range(0,5):
        new_date = new_date + split_array[i] + " "
    return new_date.rstrip()


def does_sub_exist(cur, conn, feed):
    row = (feed,)
    cur.execute('SELECT COUNT (*) FROM subscriptions WHERE feed = ?', row)
    return_string = str(cur.fetchone())[1]
    if return_string == "0":
        return 0
    else:
        return 1


def delete_subscription(cur, conn, url):
    row = (url,)
    cur.execute('DELETE FROM subscriptions WHERE feed = ?', row)
    conn.commit()


def get_name_from_feed(cur, conn, url):
    row = (url,)
    cur.execute('SELECT channel from subscriptions WHERE feed = ?', row)
    return_string = cur.fetchone()
    try:
        return_string = ''.join(return_string)
    except TypeError:
        return_string = "None"
    return str(return_string)


def list_subscriptions(cur, conn):
    count = 0
    try:
        result = cur.execute('SELECT * FROM subscriptions')
        for sub in result:
            print("Name:\t\t" + sub[0])
            print("Feed:\t\t" + sub[1])
            print("Last Ep:\t" + sub[2] + "\n")
            count += 1
        print(str(count) + " subscriptions present")
    except sqlite3.OperationalError:
        print("There are no current subscriptions or there was an error")


def get_subscriptions(cur, conn):
    try:
        cur.execute('SELECT * FROM subscriptions')
        return cur.fetchall()
    except sqlite3.OperationalError:
        print("There are no current subscriptions")
        return null


def update_subscription(cur, conn, feed, date):
    # Make sure that the date we are trying to write is newer than the last episode
    # Presumes that "null" dates will be saved in DB as 1970-01-01 (unix "start" time)
    existing_last_ep = get_last_subscription_downloaded(cur, conn, feed)
    if mktime(strptime(existing_last_ep, "%a, %d %b %Y %H:%M:%S")) <= mktime(strptime(date, "%a, %d %b %Y %H:%M:%S")):
        row = (date, feed)
        cur.execute('UPDATE subscriptions SET last_ep = ? where feed = ?', row)
        conn.commit()


def get_last_subscription_downloaded(cur, conn, feed):
    row = (feed,)
    cur.execute('SELECT last_ep FROM subscriptions WHERE feed = ?', row)
    rec = cur.fetchone()
    return rec[0]

if __name__ == "__main__":
    main(sys.argv[1:])
