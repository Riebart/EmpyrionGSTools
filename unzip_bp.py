#!/usr/bin/env python

import sys
import StringIO
import zipfile

with open(sys.argv[1],'r') as fp:
    bp = fp.read()

# Attempt to find the zip section by searching backwards for the 0x0304140000000800 string.
zipblock = "PK" + bp[bp.rfind('\x03\x04\x14\x00\x00\x00\x08\x00'):]
zf = zipfile.ZipFile(StringIO.StringIO(zipblock),'r')

# Confirm that the zip pases self-checks.
if zf.testzip() is not None:
    print "Zip failed to pass self-test."
    exit(1)

# Read the '0' file, and print it.
sys.stdout.write(zf.read('0'))
