import json, os, requests
base="http://127.0.0.1:8180/api/v1"
r=requests.post(base+"/auth/login", json={"identifier":"anas@superadmin.nt","password":os.environ["SUPER_ADMIN_PASSWORD"]}, timeout=20)
print("login", r.status_code)
assert r.ok
h={"Authorization":"Bearer "+r.json()["access_token"]}
for path in ("super-admin/health","super-admin/performance","super-admin/dashboard"):
 x=requests.get(base+"/"+path,headers=h,timeout=30); print(path,x.status_code,json.dumps(x.json(),ensure_ascii=False)[:1000]); assert x.ok
public=requests.get("http://127.0.0.1:5175/api/public/content",timeout=20); print("public",public.status_code,public.json()["branding"]["nom_clinique"],list(public.json()["expertises"])); assert public.ok
