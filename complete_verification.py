import requests, json, os
B='http://127.0.0.1:8000'; out='/home/ubuntu/audit-clinic/evidence'; os.makedirs(out,exist_ok=True)
def auth(e,p):
 s=requests.Session(); r=s.post(B+'/api/v1/auth/login',json={'identifier':e,'password':p}); r.raise_for_status(); s.headers['Authorization']='Bearer '+r.json()['access_token']; return s
d=auth('doctor@clinic.local','LocalValidationOnly-2026!')
# The lot creation response returned lot_id=2; use the actual DB lot id.
r=d.post(B+'/api/v1/injectables/utilisation',json={'lot_id':2,'patient_id':1,'praticien_id':4,'quantite':2,'unite':'unité','dossier_id':5,'type_injection':'Audit Botox Clinique','notes':'Utilisation pendant recette'}); print('injectable_usage',r.status_code,r.text[:500])
for label,url in [('dossier_detail',B+'/api/v1/patients/1/dossiers/5'),('timeline',B+'/api/v1/patients/1/dossiers'),('lots',B+'/api/v1/injectables/lots'),('tracabilite',B+'/api/v1/injectables/tracabilite/1')]:
 r=d.get(url); print(label,r.status_code,r.text[:1000]); open(out+'/'+label+'.json','w').write(r.text)
a=auth('assistante.qa@autoclinique.test','RoleQA-2026-Secure!')
r=a.get(B+'/api/v1/factures'); print('invoices',r.status_code,r.text[:1200]); open(out+'/invoices.json','w').write(r.text)
r=a.get(B+'/api/v1/factures/1/pdf'); print('invoice_again',r.status_code,r.headers.get('content-type'),len(r.content))
