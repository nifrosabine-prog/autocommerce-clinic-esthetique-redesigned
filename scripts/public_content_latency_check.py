import time, requests
base="http://127.0.0.1:8100/api/public/content"
start=time.perf_counter(); r=requests.get(base, timeout=20); elapsed=(time.perf_counter()-start)*1000
print(r.status_code, round(elapsed,2), r.json().get("branding",{}).get("nom_clinique"), list(r.json().get("expertises",{})))
raise SystemExit(0 if r.status_code == 200 else 1)
