import requests, datetime
B='http://127.0.0.1:8000'; s=requests.Session()
r=s.post(B+'/api/v1/auth/login',json={'identifier':'doctor@clinic.local','password':'LocalValidationOnly-2026!'})
print('doctor_login',r.status_code); h={'Authorization':'Bearer '+r.json()['access_token']}
payload={'praticien_id':4,'date_acte':'2026-09-15','observations':'Dossier de test audit','suivi_requis':False}
r=s.post(B+'/api/v1/patients/1/dossiers',headers=h,json=payload); print('create_dossier',r.status_code,r.text[:500])
for p in ['/api/v1/patients/1/dossiers','/api/v1/patients/1/export-structured','/api/v1/patients/1/export-pdf']:
 r=s.get(B+p,headers=h); print('GET',p,r.status_code,r.headers.get('content-type'),len(r.content),r.text[:180] if 'json' in r.headers.get('content-type','') else '')
files={'file':('audit-note.txt',b'Contenu confidentiel de recette medicale','text/plain')}
r=s.post(B+'/api/v1/patients/1/medical-documents',headers=h,files=files,data={'description':'Document de test'}); print('upload_doc',r.status_code,r.text[:500])
if r.ok:
 did=r.json().get('id'); r=s.get(B+f'/api/v1/patients/1/medical-documents/{did}/download',headers=h); print('download_doc',r.status_code,r.headers.get('content-type'),len(r.content),r.content[:80])
with open('/home/ubuntu/audit-clinic/qa_photo_avant_fake.jpg','rb') as f:
 r=s.post(B+'/api/v1/patients/1/photos?type_photo=avant',headers=h,files={'file':('qa_photo_avant_fake.jpg',f,'image/jpeg')}); print('upload_photo',r.status_code,r.text[:400])
r=s.post(B+'/api/v1/auth/login',json={'identifier':'qa.admin@clinic.local','password':'QA-Admin-2026!local'}); ha={'Authorization':'Bearer '+r.json()['access_token']}
r=s.post(B+'/api/v1/patients/1/dossiers',headers=ha,json=payload); print('admin_create_dossier',r.status_code,r.text[:300])
