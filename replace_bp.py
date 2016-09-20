#!/usr/bin/env python

# More complex script that convers locations in 3D space into a Blueprint
# dense filled matrix/block types.
#
# For now, only a Steel cube block is used.

import sys
import math
import struct
import StringIO
import zipfile
import argparse

def dbm_bitmask(dbm):
    block_strings = ""
    bm = []

    # Current mask, and the bit being twiddled.
    # When this rolls over, it gets appended to the bm list.
    cm = 0
    cb = 1

    for i in range(len(dbm)):
        x = dbm[i]
        for j in range(len(x)):
            y = x[j]
            for k in range(len(y)):
                z = y[k]
                if z != False:
                    #block_strings += "\x87\x01\x00\x00"
                    block_strings += "\x87" + \
                                     (chr(z[1]) if len(z) > 1 else chr(1)) + \
                                     chr(0) + \
                                     (chr(z[0]) if len(z) > 0 else chr(0))
                    cm += cb
                cb *= 2
                if cb > 128:
                    bm.append(cm)
                    cb = 1
                    cm = 0
    if cb > 1:
        bm.append(cm)
    return (bm, block_strings)

def sparse_to_dense(positions, meta, l, w, h):
    # Map the numeric axes, in terms of the major-ordering of the arrays, to the named axes
    Z = (l,0)
    Y = (w,1)
    X = (h,2)

    a = [[[False for z in range(Z[0])] for y in range(Y[0])] for x in range(X[0])]

    for p, m in zip(positions, meta):
        P = [p[X[1]], p[Y[1]], p[Z[1]]]
        a[P[0]][P[1]][P[2]] = m

    return a

def list_subtract(l1, l2):
    return [ l1[i] - l2[i] for i in range(len(l1)) ]

def bounding_box(positions):
    m = [ min([p[i] for p in positions]) for i in range(3) ]
    M = [ max([p[i] for p in positions]) for i in range(3) ]
    return (m, M)

def generate_blocks(positions, meta):
    # The string used for each block, corresponds to a steel cube.
    # The four bytes are (in order):
    # - Block type
    #  > 0x87 = Steel
    #  > 0x8a = Hardened Steel
    # - Rotation (Code, Forward, Up) with vectors as (x, y, z)
    #  > 0x01, +y, +z
    #  > 0x09, +x, +z
    #  > 0x11, -y, +z
    #  > 0x19, -x, +z
    #  > 0x21, +y, +x
    #  > 0x29, +z, +x
    #  > 0x31, -y, +x
    #  > 0x39, -z, +x
    #  > 0x41, -y, -z
    #  > 0x49, -x, -z
    #  > 0x51, +y, -z
    #  > 0x59, +x, -z
    #  > 0x61, +y, -x
    #  > 0x69, +z, -x
    #  > 0x71, -y, -x
    #  > 0x79, -z, -x
    #  > 0x81, +z, -y
    #  > 0x89, +x, -y
    #  > 0x91, -z, -y
    #  > 0x99, -x, -y
    #  > 0xA1, -x, +y
    #  > 0xA9, -z, +y
    #  > 0xB1, +x, +y
    #  > 0xB9, +z, +y
    # - 0x00 ???
    # - Blocktype variant
    #  > 0x14 = Slope 1:1 Solid
    #  > 0x12 = Slope 1:2 Top Solid
    #  > 0x10 = Slope 1:2 Bottom Solid
    #  > 0x00 = Full Cube
    block_type = "\x87"
    block_rotation = "\x01"
    block_shape = "\x00"
    #block_string = "\x87\x01\x00\x00"

    # Step 1: Figure out how big the bounding box is, calculate the two opposing corners.
    m, M = bounding_box(positions)

    # Step 2: Move all positions by the minimal corner, putting one corner at the origin,
    # and move the maximal corner
    length, width, height = list_subtract(M, m)
    length += 1
    width += 1
    height += 1
    sys.stderr.write("Dimensions of resulting blueprint: %d %d %d\n" % (length, width, height))
    positions = [ list_subtract(p, m) for p in positions ]
    #sys.stderr.write(repr(positions) + "\n")

    # Step 3: Now that we have the size of the object, calculate the header
    n_hdr_bytes = int(math.ceil(length * width * height / 8.0))
    sys.stderr.write("Model requires %d header bytes\n" % n_hdr_bytes)
    output = struct.pack("<L", n_hdr_bytes)

    # Step 3: Given the positions of the blocks, derive the cuboid-filling bit mask
    # for block/space. This is equivalent to convert a sparse 1-0 matrix to a dense matrix
    #
    # This just returns a dense True/False matrix, which needs to be serialized into a bitmask.
    dense_boolean_matrix = sparse_to_dense(positions, meta, length, width, height)
    bm_list, block_strings = dbm_bitmask(dense_boolean_matrix)
    output += "".join([struct.pack('B', bm) for bm in bm_list])
    set_bits = 0
    for b in bm_list:
        for i in range(8):
            if b & (1<<i):
                set_bits += 1
    print "%d bits set in header bytes for %d blocks." % (set_bits, len(positions))

    # Step 4: Fill in the body/footer with steel blocks and whatever the footer represents.
    # We need to build a mapping of positions to order to look up the positions and
    # place the right block at the right positions in the Blueprint.
    output += block_strings

    # Step 5: Fill in the footer, which we'll just ignore ... ???
    # There are four 'section', each with the same format as the block type header,
    # probably representing rotation, texture, symbol, and symbol somehow.
    output += "\x01\x7f"
    for i in xrange(4):
        output += struct.pack("<L", n_hdr_bytes)
        output += "\x00" * n_hdr_bytes

    #sys.stderr.write(output.encode("hex") + "\n")
    return (output, length, width, height)

def csv_to_array(csv):
    return [ [ int(float(i)) for i in l.strip().split(",") ] for l in csv.strip().split("\n") ]

parser = argparse.ArgumentParser(description="Given an input CSV of coordinates, modify a Blueprint to transplant the blocks into.")
parser.add_argument("--blueprint-file", required=True, help="Filename of the blueprint file to modify.")
parser.add_argument("--dimension-remap", required=False, default="1,2,3", help="A permutation of 1,2,3 to remap the coordinates. Example: 1,3,2")

pargs = parser.parse_args()

with open(pargs.blueprint_file,'r') as fp:
    bp = fp.read()

positions = csv_to_array(sys.stdin.read())

if pargs.dimension_remap != None:
    remap = [ int(i)-1 for i in pargs.dimension_remap.split(",") ]
    remap.extend([3,4])
    positions = [ tuple([p[remap[i]] for i in range(min(5,len(p)))]) for p in positions ]

new_blocks, length, width, height = generate_blocks([tuple(p[:3]) for p in positions],
                                                    [tuple(p[3:]) for p in positions])

sso = StringIO.StringIO()
zf = zipfile.ZipFile(sso, 'w', zipfile.ZIP_DEFLATED)
zf.writestr('0',new_blocks)
zf.close()

# The Empyrion Blueprints don't include the first PK, so don't read that.
sso.seek(2)
new_zip = sso.read()

# Write out:
# - The initial global header
# - Rebuild the dimensions
# - The device groupings from the original BP
# - Replace the zip section with our newly built one
new_bp = bp[:9] + \
struct.pack("<LLL",int(length),int(width),int(height)) + \
bp[21:bp.rfind('\x03\x04\x14\x00\x00\x00\x08\x00')] + \
new_zip

#sys.stdout.write(new_bp)
with open(pargs.blueprint_file,'w') as fp:
    fp.write(new_bp)
    fp.flush()
    fp.close()
