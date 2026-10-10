import sys, traceback
log = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_diag.log", "w", encoding="utf-8")
def p(*a):
    print(*a, file=log, flush=True)
p("py", sys.version)
p("path0", sys.path[:4])
try:
    import conversion
    p("conversion imported from", conversion.__file__)
    from conversion import get_model_class, ModelType, get_model_architecture
    p("symbols ok")
except Exception:
    p("IMPORT ERROR:")
    p(traceback.format_exc())
log.close()
