#!/usr/bin/env python
#-*- coding: UTF-8 -*-

from ConfigParser import SafeConfigParser
from collections import defaultdict
from optparse import OptionParser, OptionValueError
from subprocess import Popen, PIPE
import feedparser
import logging
import os
import re
import sys

try:
    from collections import OrderedDict
except ImportError:
    from odict import odict as OrderedDict

APP_NAME = "processfeed"
LOG_FILE = os.path.expanduser("~/.%s.log" % APP_NAME)
CONFIG_FILES = [os.path.expanduser("~/.%s" % APP_NAME),
    os.path.expanduser("~/%s.ini" % APP_NAME)]
VERBOSE = 20


#@builtin
#def run(command, stdin=""):
#    if stdin:
#        debug("""Starting "%s" with stdin pipe""" % command)
#        proc = Popen(command, shell=True, stdin=PIPE)
#        proc.stdin.write(stdin.encode("UTF-8", "replace"))
#        proc.stdin.close()
#        proc.wait()
#    else:
#        debug("""Starting "%s" with stdin pipe""" % command)
#        proc = Popen(command, shell=True)
#        proc.wait()
#    if proc.returncode:
#        warning("""Process '%s' exited with error %d""" % (command,
#            proc.returncode))
#    return proc.returncode


def write(text, destination):
    debug("""Writing "%s" to %s""" % (text, destination))
    f = open(destination, "a")
    f.write("%s\n" % text.encode("UTF-8", "replace"))
    f.close()


def get_depth():
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

    middle = (minn + maxn) / 2
  
    while minn < middle:
        if exist_frame(middle):
            minn = middle
        else:
            maxn = middle

        middle = (minn + maxn) / 2
  
    return max(minn - 2, 0) #4 == len(main, get_depth)


def ident(func, identation="  "):
    def decorated(message, *args, **kwargs):
        newmessage = "%s%s" % (identation * (get_depth() - 1), message)
        return func(newmessage, *args, **kwargs)
    return decorated


def read(filename):
    try:
        file = open(filename)
        lines = [unicode(line.split(" #")[0].strip(), "latin-1")
            for line in file.readlines()]
    except IOError:
        warning("%s does not exist" % filename)
        lines = []
    return lines


class Processfeed(object):

    def __init__(self, config):
        self.config = config

        sections = config.sections()
        self.actions = OrderedDict()
        for section in sections:
            if section.startswith("ACTION"):
                self.actions[section] = OrderedDict()
                self.actions[section]["_name"] = section[7:]
                for key, value in config.items(section, True):
                    self.actions[section][key] = value
                debug(self.actions[section])

        self.history = read(LOG_FILE)
    
    
    def get_entry_id(self, action, entry):
        for key in ("id", "link"):
            if key in entry:
                idstring = entry[key]
                break
        else:
            error("Entry cannot be identified, please report this bug."
                "Dump:\n%s" % entry.keys())
        return "%s::%s" % (action["_name"], idstring)


    def get_entries(self, feed):
        feed = feedparser.parse(feed)

        if "bozo_exception" in feed:
            error("Bozo exception: %s %s"
                % ("feed", feed["bozo_exception"]))
            return []
        else:
            entries = feed["entries"][::-1]
            info("Readed %d entries" % len(entries))
            return entries


    def get_news(self, action, entries=None):
        if not entries:
            entries = self.get_entries(action["feed"])

        new_entries = []
        for entry in entries:
            idstring = self.get_entry_id(action, entry)
            if idstring in self.history:
                debug("%s in history" % idstring)
            else:
                new_entries.append(entry)
            
        return new_entries


    def process_entry(self, action, entry):
        idstring = self.get_entry_id(action, entry)
        debug(idstring)

        safe_globals = {}
        safe_globals["__builtins__"] = globals()["__builtins__"]
        safe_globals["re"] = re

        safe_locals = {}
        safe_locals["entry"] = entry

        result = None
        del(action["feed"])
        for name, expression in action.iteritems():
            debug("%s = %s" % (name, expression))
            if not name.startswith("_"):
                result = eval(expression, safe_globals, safe_locals)
                safe_locals[name] = result
            else:
                safe_locals[name] = expression

            moreinfo("%s = %s" % (name, result))
            debug("safe_locals: %s" % safe_locals)

            if name.startswith("assert"):
                if not safe_locals[name]:
                    info("Ignored because assert is false.")
                    return

        write("%s #%s" % (idstring, entry["title"]), LOG_FILE)
        return result


    def process_action(self, action):
        new_entries = self.get_news(action)
        if new_entries:
            return self.process_entry(action, new_entries[0])


    def process_all(self):
        for name, action in self.actions.iteritems():
            moreinfo(name)
            debug(action)
            self.process_action(action)


def get_options():
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

    # Define the default options
    # Define the default options
    optparser.set_defaults(verbose=0, quiet=0, logfile=LOG_FILE,
        conffile="")

    # Process the options
    return optparser.parse_args()


def process(config):
    """Read the feed and execute the defined rules"""

    sections = config.sections()
    debug("Sections: %s" % sections)

    for section in sections:
        process_section(config, section)


def get_config(conf_file=None):
    'Read config files'
    config = SafeConfigParser(None, OrderedDict)
    read_from = conf_file or CONFIG_FILES
    files = config.read(read_from)
    debug("Readed config files at: %s" % files)

    return config


def main(options, args):
    """The main routine"""
    # Read the config values from the config files
    config = get_config(options.conffile)
    processfeed = Processfeed(config)
    processfeed.process_all()
    return


if __name__ == "__main__":
    # == Reading the options of the execution ==
    options, args = get_options()

    format = "%(asctime)s - %(message)s"
    logging.basicConfig(format=format, level=0)
#    logging.basicConfig(format=format, filename=LOG_FILE, level=0)
    logger = logging.getLogger()
    logger.handlers[0].setLevel(VERBOSE)

    VERBOSE = (options.quiet - options.verbose) * 10 + 30
    stderr = logging.StreamHandler()
    stderr.setLevel(VERBOSE)
    logger.addHandler(stderr)

    debug = ident(logger.debug)
    moreinfo = ident(logger.info)
    info = ident(logger.warning) # Default
    warning = ident(logger.error)
    error = ident(logger.critical)

    debug("Verbose level: %s" % VERBOSE)
    debug("""Options: '%s', args: '%s'""" % (options, args))

    exit(main(options, args))
