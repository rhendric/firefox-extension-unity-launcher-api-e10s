#!/usr/bin/env python3

import sys, json, struct, subprocess, logging, os

# Using print() for logging messages will cause the Firefox connection to
# break; FF expects everything going out stdout to adhere to the same message
# format as stdin. Using logging instead pushes messages to stderr, which
# doesn't have that constraint.
logging.basicConfig(format='%(message)s', level=logging.INFO)

application = 'firefox'

# If this process's parent is /usr/lib/<application>/firefox, use that
# application for getting the launcher (this makes this extension usable with
# /usr/lib/firefox-developer-edition/firefox, for example)
parentPath = os.path.realpath('/proc/%d/exe' % os.getppid())
parentDir, parentName = os.path.split(parentPath)
if parentName == 'firefox':
    dirDir, dirName = os.path.split(parentDir)
    if dirDir == '/usr/lib':
        application = dirName
else:
    # If Firefox isn't running this script, perhaps it's being tested from the
    # command line--enable debug logging
    logging.getLogger().setLevel(logging.DEBUG)

# try libunity
launcher = None
loop = None
previousCount = 0
previousProgress = 0.0
try:
    import gi
    gi.require_version('Unity', '7.0')
    from gi.repository import Unity, GLib
    loop = GLib.MainLoop()
    launcher = Unity.LauncherEntry.get_for_desktop_id(application + ".desktop")
    launcher.set_property('count', 0)
    launcher.set_property('count_visible', False)
    launcher.set_property('progress', 0.0)
    launcher.set_property('progress_visible', False)
    try:
        import _thread
        _thread.start_new_thread(loop.run, ())
        logging.info('thread started with loop.run()')
    except:
        logging.error('Error creating a thread')
except:
    logging.warning('libunity not found')

# read a message from stdin and decode it.
def readMessage():
    rawLength = sys.stdin.buffer.read(4)
    if len(rawLength) == 0:
        logging.info('length is empty, exiting')
        sys.exit(0)
    messageLength = struct.unpack('@I', rawLength)[0]
    message = sys.stdin.read(messageLength)
    receivedMessage = json.loads(message)
    logging.debug('receivedMessage: ' + receivedMessage)
    return receivedMessage


def processMessage(receivedMessage):

    splitted = receivedMessage.split('|')
    countMessage = splitted[0]
    progressMessage = splitted[1]

    global previousCount
    global previousProgress

    #
    # handle message with COUNT
    #
    try:
        count = int(countMessage[6:])
        if (count < 0 or count > 9999):
            logging.warning("Count has to be in range 0...9999.")
        elif (count == previousCount):
            logging.debug("Count has not changed.")
        else:
            previousCount = count
            if (count == 0):
                #
                # reset task manager entry (make count and progress invisible)
                #
                if launcher is not None:
                    launcher.set_property('count', 0)
                    launcher.set_property('count_visible', False)
                    launcher.set_property('progress', 0.0)
                    launcher.set_property('progress_visible', False)
                else:
                    subprocess.run(["gdbus", "emit", "--session", "--object-path", "/", "--signal", "com.canonical.Unity.LauncherEntry.Update", application, "{'progress-visible': <'false'>, 'count-visible': <'false'>, 'count': <'0'>, 'progress': <'0'>}"])
                return
            else:
                #
                # set task manager entry's 'count'
                #
                if launcher is not None:
                    launcher.set_property('count', count)
                    launcher.set_property('count_visible', True)
                    launcher.set_property('progress_visible', True)
                else:
                    subprocess.run(["gdbus", "emit", "--session", "--object-path", "/", "--signal", "com.canonical.Unity.LauncherEntry.Update", application, "{'progress-visible': <'true'>, 'count-visible': <'true'>, 'count': <'%d'>}" % count])
    except:
        logging.warning("Error parsing count value.")

    #
    # handle message with PROGRESS
    #
    try:
        progress = round(float(progressMessage[9:]), 2)
        if (progress < 0 or progress > 1):
            logging.warning("Progress has to be in range 0...1.")
        elif (progress == previousProgress):
            logging.debug("Progress has not changed.")
        else:
            previousProgress = progress
            logging.debug('setting progress=' + str(progress))
            #
            # set task manager entry's 'progress'
            #
            if launcher is not None:
                launcher.set_property('progress', progress)
            else:
                subprocess.run(["gdbus", "emit", "--session", "--object-path", "/", "--signal", "com.canonical.Unity.LauncherEntry.Update", application, "{'progress-visible': <'true'>, 'progress': <'%.4f'>}" % progress])
    except:
        logging.warning("Error parsing progress value.")


logging.info('start listening for messages')
while True:
    receivedMessage = readMessage()
    processMessage(receivedMessage)
