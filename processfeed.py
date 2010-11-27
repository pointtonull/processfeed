#!/usr/bin/env python2.6
#-*- coding: UTF-8 -*-

from ConfigParser import SafeConfigParser
from optparse import OptionParser, OptionValueError
from subprocess import Popen, PIPE
from collections import defaultdict
import feedparser
import os
import re
import sys

LOGFILE = os.path.expanduser("~/.processfeed.log")
CONFIGFILE = os.path.expanduser('~/.processfeed')

class Verbose:
    def __init__(self, verbosity, prefix="", ident=True):
        self.verbosity = False if verbosity < 0 else True
        self.prefix = prefix
        self.ident = ident

    def __call__(self, *args):
        if self.verbosity:
            message = " ".join((unicode(e) for e in args))
            sys.stderr.write("%s%s%s\n" % ("  " * self.get_depth(), self.prefix,
                message))

    def get_depth(self):
        if not self.ident:
            return 0
        else:
            def exist_frame(n):
                try:
                    if sys._getframe(n):
                        return True
                except ValueError:
                    return False

            now = 0
            maxn = 1
            minn = 0

            while exist_frame(maxn):
                minn = maxn
                maxn *= 2

            # minn =< depth < maxn
            middle = (minn + maxn) / 2
          
            while minn < middle:
                if exist_frame(middle):
                    minn = middle
                else:
                    maxn = middle

                middle = (minn + maxn) / 2
          
            return max(minn - 3, 0) #4 == len(main, Verbose, get_depth)



def write(text, destination):
    debug("""Writing "%s" to %s""" % (text, destination))
    f = open(destination, "a")
    f.write("%s\n" % text.encode("UTF-8", "replace"))
    f.close()


def read(filename):
    try:
        file = open(filename)
        lines = [unicode(line.split("#")[0].strip(), "latin-1")
            for line in file.readlines()]
    except IOError:
        warning("%s does not exist" % filename)
        lines = []
    return lines


def get_id(section, entry):
    for key in ("id", "link"):
        if key in entry:
            idstring = entry[key]
            break

    else:
        error("Entry cannot be identified, please report this bug."
            "Dump:\n%s" % entry.keys())

    return "%s::%s" % (section, idstring)


def run(command, stdin=""):
    """Execute the given command and pases stdin (if any) to the proc.
    """
    if stdin:
        debug("""Starting "%s" with stdin pipe""" % command)
        proc = Popen(command, shell=True, stdin=PIPE)
        proc.stdin.write(stdin.encode("UTF-8", "replace"))
        proc.stdin.close()
        proc.wait()
    else:
        debug("""Starting "%s" with stdin pipe""" % command)
        proc = Popen(command, shell=True)
        proc.wait()

    if proc.returncode:
        warning("""Process '%s' exited with error %d""" % (command,
            proc.returncode))
    return proc.returncode


def process_section(section):
    info("Processing %s" % section)
    items = defaultdict(lambda: u"None")
    for key, value in config.items(section, True):
        items[key] = value.decode("utf-8")

    enabled = items["enabled"]

    if enabled == "False":
        debug("Enabled == False")
        return

    feed = feedparser.parse(items["feed"])

    if "bozo_exception" in feed:
        error("%s %s" % (items["feed"], feed["bozo_exception"]))
        return
    else:
        info("Readed %d entries" % len(feed["entries"]))

    for entry in feed["entries"][::-1]:
        process = False
        idstring = unicode(get_id(section, entry))

        if idstring in history:
            debug("%s in history" % idstring)
        else:
            info("%s:" % idstring)
            safe_globals = {"re": re, "feed": feed, "entry": entry}
            enabled = eval(items["enabled"], safe_globals)

            if enabled:
                info("Enabled: %s" % enabled)

                info("Command code: %s" % items["command"])
                command = unicode(eval(items["command"], safe_globals))
                info("Command text: " + command.encode("ascii", "replace"))

                info("Stdin code: %s" % items["stdin"].encode("ascii",
                    "replace"))
                stdin = unicode(eval(items["stdin"], safe_globals))
                info("Stdin text: %s" % stdin.encode("ascii", "replace"))

                exitcode = run(command, stdin)
                write("%s #%s" % (idstring, entry["title"]), LOGFILE)
                return exitcode

            else:
                info("Not enabled: %s" % enabled)
                write("%s #%s (OMITED)" % (idstring, entry["title"]),
                    LOGFILE)

def get_options():
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
        "inteast of the default"), action="store", dest="conffile")
    optparser.add_option("-l", "--log", help=("Uses the given log file "
        "inteast of the default"), action="store", dest="logfile")
    optparser.add_option("-v", "--verbose", action="count", dest="verbose",
        help="Increment verbosity")
    optparser.add_option("-q", "--quiet", action="count", dest="quiet",
        help="Decrement verbosity")
    optparser.add_option("-d", metavar="VAR=VALUE", action="callback",
        callback=define_variable, type="string", nargs=1, dest="variables",
        help="Define a variable VAR to VALUE")

    # Define the default options
    optparser.set_defaults(verbose=0, quiet=0, variables={},
        conffile=CONFIGFILE, )

    # Process the options
    return optparser.parse_args()
    


def process():
    """Read the feed and execute the defined rules
    """

    sections = config.sections()
    debug("Sections: %s" % sections)

    for section in sections:
        process_section(section)



if __name__ == "__main__":
    # == Reading the options of the execution ==
    options, args = get_options()

    error = Verbose(options.verbose - options.quiet + 1, "E: ")
    info = Verbose(options.verbose - options.quiet + 0)
    warning = Verbose(options.verbose - options.quiet - 1, "W: ")
    debug = Verbose(options.verbose - options.quiet - 2, "D: ")

    debug("""Options: '%s', args: '%s'""" % (options, args))


    # Define the defaults value
    config = SafeConfigParser()

    # Read the values from the file
    config.read(CONFIGFILE)

    # Read the history log
    history = read(LOGFILE)

    exit(process())
