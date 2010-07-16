#!/usr/bin/env python2.6
#-*- coding: UTF-8 -*-

from ConfigParser import SafeConfigParser
from optparse import OptionParser, OptionValueError
from subprocess import Popen, PIPE
from decoradores import Verbose
from debug import debug
from collections import defaultdict
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
def get_id(section, entry):
    for key in ("id", "link"):
        if key in entry:
            idstring = entry[key]
            break

    else:
        debug("    E: Entry cannot be identified, please report this bug."
            "Dump:\n%s" % entry.keys())

    return "%s::%s" % (section, idstring)


@Verbose(VERBOSE)
def execute(command, stdin=""):
    if stdin:
        proc = Popen(command, shell=True, stdin=PIPE)
        proc.stdin.write(stdin.encode("UTF-8", "replace"))
        proc.stdin.close()
    else:
        proc = Popen(command, shell=True)
        proc.wait()
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

        items = defaultdict(lambda: u"None")
        for key, value in config.items(section, True):
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
            process = False
            idstring = get_id(section, entry)

            if idstring in history:
                debug("    %s in history" % idstring)
            else:
                debug("    %s:" % idstring)
                safe_globals = {"re": re, "feed": feed, "entry": entry}
                enabled = eval(items["enabled"], safe_globals)

                if enabled:
                    debug("        Enabled: %s" % enabled)

                    debug("        Command code: %s" % items["command"])
                    command = unicode(eval(items["command"], safe_globals))
                    debug("        Command text: %s" % command.encode("UTF-8"))

                    debug("        Stdin code: %s" % items["stdin"])
                    stdin = unicode(eval(items["stdin"], safe_globals))
                    debug("        Stdin text: %s" % stdin.encode("UTF-8"))

                    error = execute(command, stdin)
                    write("%s #%s" % (idstring, entry["title"]), LOGFILE)
                    return error

                else:
                    debug("        Not enabled: %s" % enabled)
                    write("%s #%s (OMITED)" % (entry["id"],
                        entry["title"]), LOGFILE)


if __name__ == "__main__":
    exit(main())
