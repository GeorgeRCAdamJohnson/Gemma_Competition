# Frontmatter guard for every SKILL.md the harness will load: PyYAML must parse it to a mapping with name+description.
# Also reproduces the batch-6 failure on the OLD locate description (must raise "mapping values are not allowed here").
import glob
import sys

import yaml

OLD = ('name: locate\ndescription: Finds the source file that DEFINES what the problem is about. Run scripts/locate.py '
       'with args {"q": "<identifiers and error text from the problem>"} BEFORE reading or editing anything.\n')
try:
    yaml.safe_load(OLD)
    print("OLD parsed (diagnosis WRONG)")
except yaml.YAMLError as e:
    print("OLD fails as on the VM:", str(e).splitlines()[0], str(e).splitlines()[1].strip())

bad = 0
for f in sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else "colab_fasteval/arms6/*/skills/*/SKILL.md")):
    t = open(f, encoding="utf-8").read()
    try:
        d = yaml.safe_load(t.split("---")[1])
        assert isinstance(d, dict) and {"name", "description"} <= set(d), d
        print("OK ", f)
    except Exception as e:
        bad += 1
        print("BAD", f, type(e).__name__, e)
sys.exit(bad)
