import sys
import rich
with open('/tmp/probe.txt', 'w') as f:
    f.write('sys.path[:5]=%r\n' % (sys.path[:5],))
    f.write('rich.__file__=%s\n' % rich.__file__)
    f.write('workspace_on_path=%s\n' % ('/tmp/w' in sys.path))
