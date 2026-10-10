"""Is the gitmoji prefix an ACTIONABLE fingerprint? Test whether change-TYPE (emoji) predicts the
fix SHAPE (lines added, files touched, hunks). If bug-emoji -> small surgical, feature-emoji -> large,
the agent can condition strategy on the emoji (a free, eval-time-available prior)."""
import json, re, os, collections, statistics as st
OUT = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_emoji_signal.log","w",encoding="utf-8")
def p(*a): print(*a, file=OUT, flush=True)
TASKS = r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\comp_files\tasks.jsonl"
recs = [json.loads(l) for l in open(TASKS, encoding="utf-8")]
emoji_pat = re.compile(r'[\U0001F000-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u2B00-\u2BFF\uFE0F]')
# map codepoints to names we care about
NAME = {'\U0001F41B':'bug','\u2728':'feature','\u267B':'refactor','\U0001F4DD':'docs',
        '\U0001F6B8':'ux','\U0001F50A':'logging','\U0001F512':'security','\U0001F5D1':'deprecate',
        '\U0001F477':'build','\u2795':'add-dep','\u2796':'rm-dep','\u2B06':'upgrade-dep'}
def first_emoji(ps):
    m = emoji_pat.findall(ps[:10])
    return m[0] if m else None
def stats(t):
    patch=t["patch"]
    add=sum(1 for l in patch.splitlines() if l.startswith('+') and not l.startswith('+++'))
    files=len({f for f in re.findall(r'\+\+\+ b/(\S+)', patch) if f.endswith('.py') and not re.search(r'(^|/)tests?/|test_|_test', f)})
    hunks=patch.count('@@ -')
    return add, files, hunks

groups=collections.defaultdict(list)
for t in recs:
    e=first_emoji(t["problem_statement"])
    key = NAME.get(e, 'OTHER' if e else 'none')
    groups[key].append(stats(t))
p(f"{'type':10} {'n':>4} {'med_add':>8} {'med_files':>10} {'med_hunks':>10} {'<=15 add %':>10}")
for k in sorted(groups, key=lambda k:-len(groups[k])):
    g=groups[k]; adds=[a for a,_,_ in g]; fs=[f for _,f,_ in g]; hs=[h for _,_,h in g]
    pct=100*sum(1 for a in adds if a<=15)/len(adds)
    p(f"{k:10} {len(g):>4} {int(st.median(adds)):>8} {int(st.median(fs)):>10} {int(st.median(hs)):>10} {pct:>9.0f}%")
p("\nREAD: if 'bug' rows show small med_add + high <=15% and 'feature' shows large, the emoji predicts")
p("fix shape -> agent can condition: bug=find+revert a deviation (small), feature=add code (large).")
OUT.close(); print("done")
