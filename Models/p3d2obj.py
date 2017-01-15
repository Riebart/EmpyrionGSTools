#!/usr/bin/env python
"""
Modified from: https://github.com/Jubjub/p3din2obj
"""

import sys
import struct


def main():
    print 'started'
    data = open('test.bin', 'rb').read()
    cursor = 0
    # start parsing
    header = struct.unpack('12sxxxxxxxxIIIIIIIIIII', data[cursor:0x40])
    cursor += 0x40
    # basic counts
    vertex_count = header[1]
    normal_count = header[2]
    uv_count = header[3]
    # tri face counts
    tri_faces_p = header[4]
    tri_faces_pn = header[5]
    tri_faces_pu = header[6]
    tri_faces_pun = header[7]
    # quad face counts
    quad_faces_p = header[8]
    quad_faces_pn = header[9]
    quad_faces_pu = header[10]
    quad_faces_pun = header[11]
    # print debug data
    print 'version %s' % header[0]
    print '%s vertices' % vertex_count
    print '%s normals' % normal_count
    print '%s uvs' % uv_count
    print '%s total tris %d %d %d %d' % (
        tri_faces_p + tri_faces_pn + tri_faces_pu + tri_faces_pun, tri_faces_p,
        tri_faces_pn, tri_faces_pu, tri_faces_pun)
    print '%s total quads %d %d %d %d' % (
        quad_faces_p + quad_faces_pn + quad_faces_pu + quad_faces_pun,
        quad_faces_p, quad_faces_pn, quad_faces_pu, quad_faces_pun)
    print 'parsed header'
    # parse vertices
    vertices = []
    for i in range(vertex_count):
        vertex = struct.unpack('fff', data[cursor:cursor + 4 * 3])
        cursor += 4 * 3
        vertices.append(vertex)
    print 'successfully parsed %s vertices' % len(vertices)
    # parse normals
    normals = []
    for i in range(normal_count):
        vertex = struct.unpack('fff', data[cursor:cursor + 4 * 3])
        cursor += 4 * 3
        normals.append(vertex)
    print 'successfully parsed %s normals' % len(normals)
    # parse uvs
    uvs = []
    for i in range(uv_count):
        vertex = struct.unpack('ff', data[cursor:cursor + 4 * 2])
        vertex = (vertex[0], 1.0 - vertex[1])
        cursor += 4 * 2
        uvs.append(vertex)
    print 'successfully parsed %s uvs' % len(uvs)
    # parse faces
    tri_faces = []
    quad_faces = []

    print 'parsing tri_p type faces @ %d' % cursor
    for i in range(tri_faces_p):
        tri_faces.append([])
        indices = struct.unpack('III', data[cursor:cursor + 4 * 3])
        indices = (indices[0] + 1, indices[1] + 1, indices[2] + 1)
        tri_faces[i].append(indices)
        cursor += 4 * 3
    for i in range(tri_faces_p):
        # empty UV index mapping
        tri_faces[i].append(())
    for i in range(tri_faces_p):
        # empty normal
        tri_faces[i].append(())
    # skip materials
    print "Skipping %d materials @ %d" % (tri_faces_p, cursor)
    cursor += tri_faces_p * 2

    if tri_faces_pn > 0:
        raise Exception('not implemented')

    print 'parsing tri_pu type faces @ %d' % cursor
    for i in range(tri_faces_pu):
        tri_faces.append([])
        indices = struct.unpack('III', data[cursor:cursor + 4 * 3])
        indices = (indices[0] + 1, indices[1] + 1, indices[2] + 1)
        tri_faces[tri_faces_p + i].append(indices)
        cursor += 4 * 3
    for i in range(tri_faces_pu):
        indices = struct.unpack('III', data[cursor:cursor + 4 * 3])
        indices = (indices[0] + 1, indices[1] + 1, indices[2] + 1)
        tri_faces[tri_faces_p + i].append(indices)
        cursor += 4 * 3
    for i in range(tri_faces_pu):
        # empty normal
        tri_faces[tri_faces_p + i].append(())
    # skip materials
    print "Skipping %d materials @ %d" % (tri_faces_pu, cursor)
    cursor += tri_faces_pu * 2

    if tri_faces_pun > 0:
        raise Exception('not implemented')

    print 'parsing quad_p type faces @ %d' % cursor
    for i in range(quad_faces_p):
        quad_faces.append([])
        indices = struct.unpack('IIII', data[cursor:cursor + 4 * 4])
        indices = (indices[0] + 1, indices[1] + 1, indices[2] + 1,
                   indices[3] + 1)
        quad_faces[i].append(indices)
        cursor += 4 * 4
    for i in range(quad_faces_p):
        # empty UV index mapping
        quad_faces[i].append(())
    for i in range(quad_faces_p):
        # empty normal
        quad_faces[i].append(())
    # skip materials
    print "Skipping %d materials @ %d" % (quad_faces_p, cursor)
    cursor += quad_faces_p * 2

    if quad_faces_pn > 0:
        raise Exception('not implemented')

    print 'parsing quad_pu type faces @ %d' % cursor
    for i in range(quad_faces_pu):
        quad_faces.append([])
        indices = struct.unpack('IIII', data[cursor:cursor + 4 * 4])
        indices = (indices[0] + 1, indices[1] + 1, indices[2] + 1,
                   indices[3] + 1)
        quad_faces[quad_faces_p + i].append(indices)
        cursor += 4 * 4
    for i in range(quad_faces_pu):
        indices = struct.unpack('IIII', data[cursor:cursor + 4 * 4])
        indices = (indices[0] + 1, indices[1] + 1, indices[2] + 1,
                   indices[3] + 1)
        quad_faces[quad_faces_p + i].append(indices)
        cursor += 4 * 4
    for i in range(quad_faces_pu):
        # empty normal
        quad_faces[quad_faces_p + i].append(())
    # skip materials
    print "Skipping %d materials @ %d" % (quad_faces_pu, cursor)
    cursor += quad_faces_pu * 2

    if quad_faces_pun > 0:
        raise Exception('not implemented')

    print 'finished parsing, starting .obj generation'
    obj = open('test.obj', 'w')
    obj.write('# generated by p3din2obj\n')
    # write vertices
    n = 0
    for vertex in vertices:
        obj.write('v %s %s %s\n' % vertex)
        n += 1
    print 'wrote %s vertices' % n
    # write normals
    n = 0
    for normal in normals:
        obj.write('v %s %s %s\n' % normal)
        n += 1
    print 'wrote %s normals' % n
    # write uvs
    n = 0
    for uv in uvs:
        obj.write('vt %s %s\n' % uv)
        n += 1
    print 'wrote %s uvs' % n
    # write tri pu faces
    n = 0
    for f in tri_faces:
        if len(f[1]) > 0:
            obj.write('f %s/%s %s/%s %s/%s\n' % (f[0][0], f[1][0], f[0][1],
                                                 f[1][1], f[0][2], f[1][2]))
        else:
            obj.write('f %s %s %s\n' % (f[0][0], f[0][1], f[0][2]))
        n += 1
    print 'wrote %s tri pu faces' % n
    # write quad pu faces
    n = 0
    for f in quad_faces:
        if len(f[1]) > 0:
            obj.write('f %s/%s %s/%s %s/%s %s/%s\n' %
                      (f[0][0], f[1][0], f[0][1], f[1][1], f[0][2], f[1][2],
                       f[0][3], f[1][3]))
        else:
            obj.write('f %s %s %s %s\n' % (f[0][0], f[0][1], f[0][2], f[0][3]))
        n += 1
    print 'wrote %s quad pu faces' % n
    # finished
    obj.close()
    print 'done'


if __name__ == '__main__':
    main()
