#!/usr/bin/env python2.6
#-*- coding: UTF-8 -*-

from ConfigParser import SafeConfigParser
from optparse import OptionParser, OptionValueError
from subprocess import Popen, PIPE
import feedparser
import os
import re

LOGFILE = os.path.expanduser("~/.processfeed.log")
CONFIGFILE = os.path.expanduser('~/.processfeed')


def write(text, destination):
    f = open(destination, "a")
    f.write("%s\n" % text)
    f.close()


def read(filename):
    try:
        lines = [line.split("#")[0].strip()
            for line in open(filename).readlines()]
    except IOError:
        lines = []
    return lines


def execute(command, stdin):
    proc = Popen(command, shell=True, stdin=PIPE)
    proc.stdin.write(stdin)
    proc.stdin.close()
    return proc.returncode


def main():
    # Define the defaults value
    config = SafeConfigParser()

    # Read the values on the file
    config.read(CONFIGFILE)

    history = read(LOGFILE)

    print "Checkpoint"

    for section in config.sections():
        print section
        items = dict(config.items(section, True))
        enabled = items["enabled"]

        if enabled == "False":
            print "Continue"
            continue

        feed = feedparser.parse(items["feed"])
        
        for entry in feed["entries"][::-1]:
            if entry["id"] in history:
                print "In history"
                continue

            safe_globals = {"re": re, "feed": feed, "entry": entry}
            if eval(items["enabled"], safe_globals):
                write("%s #%s" % (entry["id"], entry["title"]), LOGFILE)
                stdin = eval(items["stdin"], safe_globals)
                command = items["command"]
                return execute(command, stdin)
            else:
                print eval(items["enabled"], safe_globals)
                write("%s #%s (OMITED)" % (entry["id"],
                    entry["title"]), LOGFILE)


if __name__ == "__main__":
    exit(main())
