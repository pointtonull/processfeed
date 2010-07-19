#!/usr/bin/env python2.6
#-*- coding: UTF-8 -*-

from ConfigParser import SafeConfigParser
from optparse import OptionParser, OptionValueError
from subprocess import Popen, PIPE
from collections import defaultdict
import feedparser
import os
import re
import time
import sys

STARTTIME = time.time()
LOGFILE = os.path.expanduser("~/.processfeed.log")
CONFIGFILE = os.path.expanduser('~/.processfeed')

class Verbose:
    def __init__(self, verbosity):
        self.verbosity = False if verbosity < 0 else True

    def __call__(self, *args):
        if self.verbosity:
            message = " ".join((str(e) for e in args))
            sys.stderr.write("%7.2f %s\n" % (time.time() - STARTTIME, message))


def write(text, destination):
    f = open(destination, "a")
    f.write("%s\n" % text.encode("UTF-8", "replace"))
    f.close()


def read(filename):
    try:
        lines = [line.split("#")[0].strip()
            for line in open(filename).readlines()]
    except IOError:
        lines = []
    return lines


def get_id(section, entry):
    for key in ("id", "link"):
        if key in entry:
            idstring = entry[key]
            break

    else:
        debug("    E: Entry cannot be identified, please report this bug."
            "Dump:\n%s" % entry.keys())

    return "%s::%s" % (section, idstring)


def execute(command, stdin=""):
    if stdin:
        proc = Popen(command, shell=True, stdin=PIPE)
        proc.stdin.write(stdin.encode("UTF-8", "replace"))
        proc.stdin.close()
        proc.wait()
    else:
        proc = Popen(command, shell=True)
        proc.wait()
    return proc.returncode


def process():
    # Define the defaults value
    config = SafeConfigParser()

    # Read the values from the file
    config.read(CONFIGFILE)



    # == Execution ==

    history = read(LOGFILE)

    sections = config.sections()
    debug("Sections: %s" % sections)

    for section in sections:
        debug("  Processing %s" % section)

        items = defaultdict(lambda: u"None")
        for key, value in config.items(section, True):
            items[key] = value.decode("utf-8")

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
                    write("%s #%s (OMITED)" % (idstring, entry["title"]),
                        LOGFILE)


if __name__ == "__main__":
    # == Reading the options of the execution ==

    def define_variable(option, opt_str, value, parser):
        """Handle the -d/--define option and populate the variables dict"""
        logging.debug(option.dest)
        logging.debug(value)
        variables = getattr(parser.values, option.dest)

        try:
            variable = re.search(r"".join(("^\s*([a-zA-Z_][a-zA-Z\d_]*)",
                "\s*=\s*(.*)\s*$")), value).groups()
        except AttributeError:
            raise OptionValueError("Declaración incorrecta: %s" % value)
        else:
            variables.update((variable,))

        logging.debug(variables)

    # Instance the parser and define the usage message
    optparser = OptionParser(usage="""
    %prog [-vqdsc]""", version="%prog .2")

    # Define the options and the actions of each one
    optparser.add_option("-s", "--section", help=("Process only the given "
        "section"), action="store", dest="section")
    optparser.add_option("-c", "--config", help=("Uses the given conf file "
        "inteast the default"), action="store", dest="conffile")
    optparser.add_option("-v", "--verbose", action="count", dest="verbose",
        help="Increment verbosity")
    optparser.add_option("-q", "--quiet", action="count", dest="quiet",
        help="Decrement verbosity")
    optparser.add_option("-d", metavar="VAR=VALUE", action="callback",
        callback=define_variable, type="string", nargs=1, dest="variables",
        help="Define a variable VAR to VALUE")

    # Define the default options
    optparser.set_defaults(verbose=0, quiet=0, variables={},
        conffile=CONFIGFILE)

    # Process the options
    options, args = optparser.parse_args()

    debug = Verbose(options.verbose - options.quiet - 2)
    info = Verbose(options.verbose - options.quiet - 1)
    warning = Verbose(options.verbose - options.quiet - 0)
    error = Verbose(options.verbose - options.quiet + 1)

    debug(options, args)

    exit(process())
