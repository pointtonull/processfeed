#!/usr/bin/env python2.6
#-*- coding: UTF-8 -*-

from ConfigParser import SafeConfigParser
from optparse import OptionParser, OptionValueError
from subprocess import Popen, PIPE
from decoradores import Verbose
from debug import debug
import feedparser
import os
import re

LOGFILE = os.path.expanduser("~/.processfeed.log")
CONFIGFILE = os.path.expanduser('~/.processfeed')
VERBOSE = 2

@Verbose(VERBOSE)
def write(text, destination):
    f = open(destination, "a")
    f.write("%s\n" % text.encode("UTF-8", "replace"))
    f.close()


@Verbose(VERBOSE)
def read(filename):
    try:
        lines = [line.split("#")[0].strip()
            for line in open(filename).readlines()]
    except IOError:
        lines = []
    return lines


@Verbose(VERBOSE)
def execute(command, stdin):
    proc = Popen(command, shell=True, stdin=PIPE)
    proc.stdin.write(stdin.encode("UTF-8", "replace"))
    proc.stdin.close()
    return proc.returncode


@Verbose(VERBOSE)
def main():
    # Define the defaults values
    config = SafeConfigParser()

    # Read the values from the file
    config.read(CONFIGFILE)

    history = read(LOGFILE)

    sections = config.sections()
    debug("Sections: %s" % sections)

    for section in sections:
        debug("  Processing %s" % section)

        items = dict(config.items(section, True))
        for key, value in items.iteritems():
            items[key] = unicode(value)

        enabled = items["enabled"]

        if enabled == "False":
            debug("    Enabled == False")
            continue

        feed = feedparser.parse(items["feed"])

        if "bozo_exception" in feed:
            debug("    %s %s" % (items["feed"], feed["bozo_exception"]))
            continue
        else:
            debug("    Readed %d entries" % len(feed["entries"]))

        for entry in feed["entries"][::-1]:
            if entry["id"] in history:
                debug("    %s in history" % entry["id"])
                continue
            else:
                debug("    %s:" % entry["id"])

            safe_globals = {"re": re, "feed": feed, "entry": entry}
            enabled = eval(items["enabled"], safe_globals)

            if enabled:
                debug("        Enabled: %s" % enabled)
                debug("        Stdin code: %s" % items["stdin"])
                stdin = eval(items["stdin"], safe_globals)
                debug("        Stdin text: %s" % stdin.encode("UTF-8"))
                command = items["command"]
                error = execute(command, stdin)
                write("%s #%s" % (entry["id"], entry["title"]), LOGFILE)
                return error

            else:
                debug("        Not enabled: %s" % enabled)
                write("%s #%s (OMITED)" % (entry["id"],
                    entry["title"]), LOGFILE)


if __name__ == "__main__":
    exit(main())
