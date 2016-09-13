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

def dbm_bitmask(dbm):
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
                #sys.stderr.write("%d %d %d " % (i,j,k) + str(z) + "\n")
                cm += z * cb
                cb *= 2
                if cb > 128:
                    bm.append(cm)
                    cb = 1
                    cm = 0
    bm.append(cm)
    return bm

def sparse_to_dense(positions, l, w, h):
    Z = (l,0)
    Y = (w,1)
    X = (h,2)

    a = [[[False for z in range(Z[0])] for y in range(Y[0])] for x in range(X[0])]

    for p in positions:
        P = [p[X[1]], p[Y[1]], p[Z[1]]]
        a[P[0]][P[1]][P[2]] = True

    #sys.stderr.write(repr(a) + "\n")
    return a

def list_subtract(l1, l2):
    return [ l1[i] - l2[i] for i in range(len(l1)) ]

def bounding_box(positions):
    m = [ min([p[i] for p in positions]) for i in range(3) ]
    M = [ max([p[i] for p in positions]) for i in range(3) ]
    return (m, M)

def generate_blocks(positions_csv):
    # The string used for each block, corresponds to a steel cube.
    block_string = "\x87\x01\x00\x00"

    # Step 0: Convert the CSV to the array
    positions = [ [ int(float(i)) for i in l.strip().split(",") ] for l in positions_csv.strip().split("\n") ]

    # Step 1: Figure out how big the bounding box is, calculate the two opposing corners.
    m, M = bounding_box(positions)

    # Step 2: Move all positions by the minimal corner, putting one corner at the origin,
    # and move the maximal corner
    length, width, height = list_subtract(M, m)
    length += 1
    width += 1
    height += 1
    sys.stderr.write("%d %d %d\n" % (length, width, height))
    positions = [ list_subtract(p, m) for p in positions ]
    #sys.stderr.write(repr(positions) + "\n")

    # Step 3: Now that we have the size of the object, calculate the header
    n_hdr_bytes = int(math.ceil(length * width * height / 8.0))
    sys.stderr.write("%d\n" % n_hdr_bytes)
    output = struct.pack("<L", n_hdr_bytes)

    # Step 3: Given the positions of the blocks, derive the cuboid-filling bit mask
    # for block/space. This is equivalent to convert a sparse 1-0 matrix to a dense matrix
    #
    # This just returns a dense True/False matrix, which needs to be serialized into a bitmask.
    dense_boolean_matrix = sparse_to_dense(positions, length, width, height)
    bm_list = dbm_bitmask(dense_boolean_matrix)
    output += "".join([struct.pack('B', bm) for bm in bm_list])

    # Step 4: Fill in the body/footer with steel blocks and whatever the footer represents.
    output += len(positions) * block_string

    # Step 5: Fill in the footer, which we'll just ignore ... ???
    # There are four 'section', each with the same format as the block type header,
    # probably representing rotation, texture, symbol, and symbol somehow.
    output += "\x01\x7f"
    for i in xrange(4):
        output += struct.pack("<L", n_hdr_bytes)
        output += "\x00" * n_hdr_bytes

    #sys.stderr.write(output.encode("hex") + "\n")
    return (output, length, width, height)

bp_filename = sys.argv[1]
#length, width, height = sys.argv[2:5]

with open(bp_filename,'r') as fp:
    bp = fp.read()

new_blocks, length, width, height = generate_blocks(sys.stdin.read())

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
with open(bp_filename,'w') as fp:
    fp.write(new_bp)
