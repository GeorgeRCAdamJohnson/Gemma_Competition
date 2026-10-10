import re, sys
p = r'C:/Users/Biges/.kiro/sessions/857524a8a80cd052/sess_b454638e-d04d-439d-a549-3d54dbf4eee2/tool-outputs/execute_pwsh-51079d1f.txt'
txt = open(p, encoding='utf-8', errors='ignore').read()
slugs = sorted(set(re.findall(r'"slug":\s*"([^"]+)"', txt)))
for s in slugs:
    print(s)
