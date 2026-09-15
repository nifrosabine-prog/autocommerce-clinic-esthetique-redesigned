import os, requests
B='http://127.0.0.1:8002'; out='/home/ubuntu/audit-clinic/evidence_branding'; os.makedirs(out,exist_ok=True)
s=requests.Session(); r=s.post(B+'/api/v1/auth/login',json={'identifier':'admin@clinic.local','password':'LocalValidationOnly-2026!'}); print('login',r.status_code); r.raise_for_status(); s.headers['Authorization']='Bearer '+r.json()['access_token']
with open('/home/ubuntu/upload/file_00000000f5588230bb37c3a2d1afe57d.png','rb') as f:
 r=s.post(B+'/api/v1/settings/branding/logo',files={'file':('clinic-logo.png',f,'image/png')}); print('upload_logo',r.status_code,r.text); r.raise_for_status(); logo=r.json()['logo_url']
r=s.patch(B+'/api/v1/settings/branding',json={'nom_clinique':'AutoCommerce Clinic Demo','couleur_primaire':'#0F766E','couleur_secondaire':'#0F172A'}); print('branding_update',r.status_code,r.text); r.raise_for_status()
assistant=requests.Session(); r=assistant.post(B+'/api/v1/auth/login',json={'identifier':'assistante.qa@autoclinique.test','password':'RoleQA-2026-Secure!'}); r.raise_for_status(); assistant.headers['Authorization']='Bearer '+r.json()['access_token']
r=assistant.get(B+'/api/v1/factures/4/pdf'); print('invoice_pdf',r.status_code,len(r.content),r.headers.get('content-type')); r.raise_for_status(); open(out+'/facture_brandee_4.pdf','wb').write(r.content)
med=requests.Session(); r=med.post(B+'/api/v1/auth/login',json={'identifier':'doctor@clinic.local','password':'LocalValidationOnly-2026!'}); r.raise_for_status(); med.headers['Authorization']='Bearer '+r.json()['access_token']
r=med.get(B+'/api/v1/patients/1/export-pdf'); print('dossier_pdf',r.status_code,len(r.content),r.headers.get('content-type')); r.raise_for_status(); open(out+'/dossier_brandee.pdf','wb').write(r.content)
print('logo_url',logo)
