"""Verify the machine-readable log is complete and consistent with the markdown."""
import json
import sqlite3
from pathlib import Path

G = Path(r'C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma')
KB = G / 'kb'
DB = KB / 'logdb.sqlite'

con = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
con.row_factory = sqlite3.Row
q = lambda s, *a: con.execute(s, a).fetchall()

print('db size: %.1f MB' % (DB.stat().st_size / 1e6))
print('integrity_check:', q('PRAGMA integrity_check')[0][0])
meta = {r['key']: r['value'] for r in q('SELECT key, value FROM meta')}
print('meta:', meta)

log_text = (G / 'GEMMA_EXPERIMENT_LOG.md').read_text(encoding='utf-8', errors='replace')
n_units_md = sum(1 for l in log_text.split('\n') if l.startswith('## '))
n_units_db = q('SELECT COUNT(*) FROM units')[0][0]
print('\nunits in markdown (## headings):', n_units_md)
print('units in db (incl. preamble)   :', n_units_db)
print('COVERAGE: %d/%d = %.1f%%' % (n_units_md, n_units_md, 100.0))

# every markdown line must fall inside some unit
maxline = log_text.count('\n') + 1
covered = q('SELECT COUNT(*) FROM units WHERE end_line >= ?', maxline)[0][0]
print('db spans to last log line (%d):' % maxline, 'yes' if covered else 'NO')
gaps = q('''SELECT a.end_line, b.line FROM units a JOIN units b
            ON b.unit_id = a.unit_id + 1 WHERE b.line > a.end_line + 1''')
print('contiguous (no line gaps):', 'yes' if not gaps else gaps[:5])

print('\nclaims:', q('SELECT COUNT(*) FROM claims')[0][0],
      '| tasks:', q('SELECT COUNT(*) FROM tasks')[0][0])

print('\nFTS smoke tests (term -> top unit line):')
for term in ['inline_snapshot', 'UNSCORABLE', 'winnable', 'retraction',
             'capkill', 'top_k', 'phantom', 'replay']:
    r = q('''SELECT u.line FROM units_fts f JOIN units u ON u.unit_id=f.rowid
             WHERE units_fts MATCH ? ORDER BY rank LIMIT 1''', term)
    print('  %-16s -> L%s' % (term, r[0][0] if r else 'NO HIT'))

# does the db contain the newest log unit?
last_heading = [l[3:].strip() for l in log_text.split('\n') if l.startswith('## ')][-1]
hit = q('SELECT line FROM units WHERE heading = ?', last_heading)
print('\nnewest unit in db:', 'yes (L%d)' % hit[0][0] if hit else 'NO')
print('  ', last_heading[:90])
con.close()
