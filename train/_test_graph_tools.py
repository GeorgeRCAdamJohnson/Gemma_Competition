import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "local_eval"))
from graph_tools import GraphTools
OUT = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_test_graph_tools.log","w",encoding="utf-8")
def p(*a): print(*a, file=OUT, flush=True)

# fastapi_14479 base_commit 2b212ddd..., gold symbol analyze_param in dependencies/utils.py
gt = GraphTools("fastapi", "2b212ddd7604891d42e2ffbafe764c334230bdb7")
p("available:", gt.available)
# 1. search by the symbol the problem would hint
r = gt.search_similar_code("analyze_param", k=5); p("search 'analyze_param':", r)
# 2. search by a CONCEPT symbol (the SSE case analog) - try 'get_dependant'
r = gt.search_similar_code("get_dependant", k=5); p("search 'get_dependant':", r)
# 3. neighbors of analyze_param
r = gt.get_code_neighbors("analyze_param", max_neighbors=8); p("neighbors analyze_param:", json.dumps(r)[:400])
# 4. node text retrieval
txt = gt.get_node_text("analyze_param"); p("analyze_param text[:200]:", (txt or "")[:200])
# 5. SSE concept on 15588's commit
gt2 = GraphTools("fastapi", "cb83b83dcf78eab4ea17d504db5abcda705fbdc4")
p("\n15588 available:", gt2.available)
p("search 'ServerSentEvent':", gt2.search_similar_code("ServerSentEvent", k=5))
p("search 'EventSourceResponse':", gt2.search_similar_code("EventSourceResponse", k=5))
OUT.close(); print("done")
