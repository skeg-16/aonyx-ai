from app.orchestrator.tools import safe_calc as c

cases = {
    "1+1": "2", "(3+4)*2": "14", "-5+10/4": "-2.5", "2**10": "1024",
}
bad = ['__import__("os")', '"a"+"b"', "True+1", "[1]", "abs(1)"]
ok = True
for e, want in cases.items():
    r = c({"expression": e})
    good = r["status"] == "ok" and r["data"] == want
    ok &= good
    print("PASS" if good else "FAIL", e, "->", r["data"])
for e in bad:
    r = c({"expression": e})
    good = r["status"] == "error"
    ok &= good
    print("PASS" if good else "FAIL", "rejects", e)
print("ALL OK" if ok else "FAILURES")
