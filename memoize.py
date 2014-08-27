#!/usr/bin/python

import sys
import os
import os.path
import re
import md5
import tempfile
import cPickle
from getopt import getopt

# if set us modification time instead of MD5-sum as check
OPT_USE_MODTIME = False

OPT_DIRS = ['.']

SYS_CALLS = ["open", "openat", "stat", "stat64", "statfs", "access"]
SYS_CALLS_AT = ["openat"]

# TODO: Check if call is successful, doesn't end with
RX = re.compile(r'.*\b(?:' + ('|').join(SYS_CALLS) + ')\("(.*)", .*')

def set_use_modtime(use):
    OPT_USE_MODTIME = use

def add_relevant_dir(d):
    OPT_DIRS.append(d)

def md5sum(fname):
    try:
        data = file(fname).read()
    except:
        data = None

    if data == None:
        return 'bad'
    else:
        return md5.new(data).hexdigest()

def modtime(fname):
    try:
        return os.path.getmtime(fname)
    except:
        return 'bad'

def files_up_to_date(files):
    for (fname, md5, mtime) in files:
        if OPT_USE_MODTIME:
            if modtime(fname) != mtime:
                return False
        else:
            if md5sum(fname) != md5:
                return False
    return True

def is_relevant(fname):
    path1 = os.path.abspath(fname)
    for dir_ in OPT_DIRS:
        path2 = os.path.abspath(dir_)
        if path1.startswith(path2):
            return True
    return False

def generate_deps(cmd):
    print 'running', cmd

    outfile = tempfile.mktemp()

    # TODO: Detect solaris and use truss instead and verify parsing of its output format
    os.system(('strace -f -o %s -e trace=' +
               ",".join(SYS_CALLS) +
               ',exit_group %s') % (outfile, cmd))
    output = file(outfile).readlines()
    os.remove(outfile)

    status = 0
    files = []
    files_dict = {}
    for line in output:
        match = (re.match(RX, line))
        if match:
            fname = os.path.normpath(match.group(1))
            print "match:", line.strip()
            if (is_relevant(fname) and
                os.path.isfile(fname)
                and not files_dict.has_key(fname)):
                files.append((fname, md5sum(fname), modtime(fname)))
                files_dict[fname] = True

        match = re.match(r'.*exit_group\((.*)\).*', line)
        if match:
            status = int(match.group(1))

    return (status, files)

def read_deps(depsname):
    try:
        f = file(depsname, 'rb')
    except:
        f = None

    if f:
        deps = cPickle.load(f)
        f.close()
        return deps
    else:
        return {}

def write_deps(depsname, deps):
    f = file(depsname, 'wb')
    cPickle.dump(deps, f)
    f.close()

def memoize_with_deps(depsname, deps, cmd):
    files = deps.get(cmd, [('aaa', '', '')])
    if not files_up_to_date(files):
        (status, files) = generate_deps(cmd)
        if status == 0:
            deps[cmd] = files
        elif deps.has_key(cmd):
            del deps[cmd]
        write_deps(depsname, deps)
        return status
    else:
        print 'up to date:', cmd
        return 0

default_depsname = '.deps'
default_deps = read_deps(default_depsname)

def memoize(cmd):
    return memoize_with_deps(default_depsname, default_deps, cmd)

if __name__ == '__main__':
    (opts, cmd) = getopt(sys.argv[1:], 'td:')
    cmd = ' '.join(cmd)
    for (opt, value) in opts:
        if opt == '-t':
            OPT_USE_MODTIME = True
        elif opt == '-d':
            OPT_DIRS.append(value)

    status = memoize(cmd)
    sys.exit(status)
