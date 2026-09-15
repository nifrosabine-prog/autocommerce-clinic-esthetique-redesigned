import json, os, sys
import requests
BASE='http://127.0.0.1:8000'
users=[('admin','qa.admin@clinic.local','QA-Admin-2026!local'),('doctor','doctor@clinic.local','LocalValidationOnly-2026!')]
for label,email,pw in users:
    s=requests.Session()
    r=s.post(BASE+'/api/v1/auth/login',json={'identifier':email,'password':pw})
    print(label,'login',r.status_code,r.text[:300])
    if r.ok:
        data=r.json(); tok=data.get('access_token')
        h={'Authorization':'Bearer '+tok} if tok else {}
        me=s.get(BASE+'/api/v1/auth/me',headers=h)
        print(label,'me',me.status_code,me.text[:300])
        for path in ['/api/v1/dashboard','/api/v1/agenda','/api/v1/patients','/api/v1/stock','/api/v1/factures','/api/v1/medical-files','/api/v1/dossier-medical']:
            x=s.get(BASE+path,headers=h)
            print(label,path,x.status_code,x.text[:160].replace('\n',' '))
# public endpoints from OpenAPI
spec=requests.get(BASE+'/openapi.json').json()
print('openapi_paths',len(spec.get('paths',{})))
for p in sorted(spec.get('paths',{})):
    if 'public' in p or 'health' in p:
        print('PUBLIC',p,','.join(spec['paths'][p].keys()))
