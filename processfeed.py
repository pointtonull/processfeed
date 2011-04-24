#!/usr/bin/env python
#-*- coding: UTF-8 -*-
"""
    Very sexy script to process feed using simple rules
"""

from ConfigParser import SafeConfigParser
from optparse import OptionParser
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


def write(text, destination):
    """
    Short cut to append text to destination and flush that
    """
    DEBUG("""write::writing "%s" to %s""" % (text, destination))
    fileo = open(destination, "a")
    fileo.write("%s\n" % text.encode("UTF-8", "replace"))
    fileo.close()


def get_depth():
    """
    Returns the current recursion level. Nice to look and debug
    """
    def exist_frame(number):
        """
        True if frame number exists
        """
        try:
            if sys._getframe(number):
                return True
        except ValueError:
            return False

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

    return max(minn - 4, 0)


def ident(func, identation="  "):
    """
    Decorates func to add identation prior arg[0]
    """
    def decorated(message, *args, **kwargs):
        newmessage = "%s%s" % (identation * (get_depth() - 1), message)
        return func(newmessage, *args, **kwargs)
    return decorated


def read(filename):
    """
    Short cut to read a file, split the comments and return lines
    """
    DEBUG("""read::reading "%s""" % filename)
    try:
        fileo = open(filename)
        lines = [unicode(line.split(" #")[0].strip(), "latin-1")
            for line in fileo.readlines()]
    except IOError:
        WARNING("%s does not exist" % filename)
        lines = []
    DEBUG("""read::readed %d lines""" % len(lines))
    return lines


def get_entry_id(action, entry):
    """
    Returns a unique action/entry name for consistency
    """
    for key in ("id", "link"):
        if key in entry:
            idstring = entry[key]
            break
    else:
        ERROR("Entry cannot be identified, please report this bug."
            "Dump:\n%s" % entry.keys())
    entry_id = "%s::%s" % (action["_name"], idstring)
    DEBUG("get_entry_id::return %s" % entry_id)
    return entry_id


def get_entries(feed):
    """
    Fetch and parse the feed and returns that in cronological order.
    """
    feed = feedparser.parse(feed)

    if "bozo_exception" in feed:
        WARNING("Bozo exception: %s %s"
            % ("feed", feed["bozo_exception"]))
        return []
    else:
        entries = feed["entries"][::-1]
        MOREINFO("Readed %d entries" % len(entries))
        return entries


def process_entry(action, entry):
    """
    Executes the action rules with entry
    """
    DEBUG("Processfeed::process_entry::%s" % entry["_id"])

    safe_globals = {}
    safe_globals["__builtins__"] = globals()["__builtins__"]
    safe_globals["re"] = re

    safe_locals = {}
    safe_locals["entry"] = entry

    result = None
    del(action["feed"]) #FIXME: Fetching must be explicit
    for name, expression in action.iteritems():
        DEBUG("Processfeed::process_entry::%s = %s" % (name, expression))
        if name.startswith("_"):
            safe_locals[name] = expression
        else:
            result = eval(expression, safe_globals, safe_locals)
            safe_locals[name] = result
        MOREINFO("%s = %s" % (name, safe_locals[name]))

        if name.startswith("assert"):
            if not safe_locals[name]:
                INFO("Ignored because assert is false.")
                break

    write("%s #(%s) %s" % (entry["_id"], result, entry["title"]), LOG_FILE)
    return result


class Processfeed(object):
    """
    The statefull main class
    """
    def __init__(self, config):
        """
        A rules set manager

        config: a ConfigParse/SafeConfigParser instance
        """

        self._config = config

        sections = config.sections()
        self.actions = OrderedDict()
        for section in sections:
            if section.startswith("ACTION"):
                self.actions[section] = OrderedDict()
                self.actions[section]["_name"] = section[7:]
                for key, value in config.items(section, True):
                    self.actions[section][key] = value
                DEBUG(self.actions[section])
            else:
                MOREINFO("""Section "%s" is ignored""" % section)

        self.history = read(LOG_FILE)


    def get_news(self, action, entries=None):
        """
        Filter out the entries already processed. If not entries will fetch
        these.
        """
        if not entries:
            DEBUG("Processfeed::get_news::fetching entries")
            entries = get_entries(action["feed"])

        new_entries = []
        for entry in entries:
            entry["_id"] = get_entry_id(action, entry)
            if entry["_id"] in self.history:
                DEBUG("Processfeed::get_news::%s in history" % entry["_id"])
            else:
                MOREINFO("%s is a novelty" % entry["_id"])
                new_entries.append(entry)
        if not new_entries:
            INFO("Without novelties")

        return new_entries


    def process_action(self, action):
        """
        Run the rules of action with the oldest novelty
        """
        INFO(action["_name"])
        new_entries = self.get_news(action)
        if new_entries:
            return process_entry(action, new_entries[0])


    def process_all_actions(self):
        """
        Run .process_action with each and every one of actions
        """
        for action in self.actions.itervalues():
            DEBUG("Processfeed::process_all_actions::%s" % action)
            self.process_action(action)


def get_options():
    """
    Parse the arguments
    """
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
    options, args = optparser.parse_args()
    return options, args


def get_config(conf_file=None):
    """
    Read config files
    """
    config = SafeConfigParser(None, OrderedDict)
    read_from = conf_file or CONFIG_FILES
    files = config.read(read_from)
    DEBUG("get_config::readed %s" % files)

    return config


def main(options, args):
    """The main routine"""
    # Read the config values from the config files
    config = get_config(options.conffile)
    processfeed = Processfeed(config)
    processfeed.process_all_actions()


if __name__ == "__main__":
    # == Reading the options of the execution ==
    options, args = get_options()

    VERBOSE = (options.quiet - options.verbose) * 10 + 30
    format_str = "%(message)s"
    logging.basicConfig(format=format_str, level=VERBOSE)
    logger = logging.getLogger()

    DEBUG = ident(logger.debug) # For developers
    MOREINFO = ident(logger.info) # Plus info
    INFO = ident(logger.warning) # Default
    WARNING = ident(logger.error) # Non critical errors
    ERROR = ident(logger.critical) # Critical (will break)

    DEBUG("get_options::options: %s" % options)
    DEBUG("get_options::args: %s" % args)

    DEBUG("Verbose level: %s" % VERBOSE)
    exit(main(options, args))
