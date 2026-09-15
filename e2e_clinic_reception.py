import base64, json, os, requests
from datetime import datetime, timedelta
B='http://127.0.0.1:8000'; OUT='/home/ubuntu/audit-clinic/evidence'; os.makedirs(OUT, exist_ok=True)

def login(email,pw):
 s=requests.Session(); r=s.post(B+'/api/v1/auth/login',json={'identifier':email,'password':pw}); print('LOGIN',email,r.status_code); r.raise_for_status(); s.headers.update({'Authorization':'Bearer '+r.json()['access_token']}); return s

def call(label, r, expected=None):
 print(label, r.status_code, r.text[:500] if 'json' in r.headers.get('content-type','') else r.headers.get('content-type',''))
 if expected and r.status_code not in expected: raise RuntimeError(f'{label}: {r.status_code} {r.text}')
 if r.headers.get('content-type','').startswith('application/json'): return r.json()
 return r

admin=login('qa.admin@clinic.local','QA-Admin-2026!local')
assistant=login('assistante.qa@autoclinique.test','RoleQA-2026-Secure!')
doctor=login('doctor@clinic.local','LocalValidationOnly-2026!')
# Configuration: verify team, create unique priced act, injectable product and lot.
team=call('team',admin.get(B+'/api/v1/equipe/membres'),{200}); print('team_members',[(x.get('id'),x.get('role'),x.get('email')) for x in team])
acts=call('acts',admin.get(B+'/api/v1/settings/actes'),{200}); act=next((x for x in acts if x.get('nom')=='Audit Botox Clinique'),None)
if not act: act=call('create_act',admin.post(B+'/api/v1/settings/actes',json={'nom':'Audit Botox Clinique','categorie':'injectable','duree_minutes':30,'prix_base':320,'description':'Acte de recette clinique','protocole':'Injection de recette','is_active':True,'is_public':True}),{200,201})
act_id=act.get('id'); print('ACT_ID',act_id)
products=call('injectable_products',admin.get(B+'/api/v1/injectables/produits'),{200}); prod=next((x for x in products if x.get('nom')=='Botox Audit Clinique'),None)
if not prod: prod=call('create_product',admin.post(B+'/api/v1/injectables/produits',json={'nom':'Botox Audit Clinique','fabricant':'Audit Lab','categorie':'toxine','unite':'unité','prix_achat':80,'prix_vente':120,'stock_minimum':5,'stock_alerte':10}),{200,201})
prod_id=prod.get('id'); print('PRODUCT_ID',prod_id)
lots=call('lots_before',admin.get(B+'/api/v1/injectables/lots'),{200}); lot=next((x for x in lots if x.get('produit_id')==prod_id and x.get('numero_lot')=='AUDIT-2026-09'),None)
if not lot:
 lot=call('create_lot',admin.post(B+'/api/v1/injectables/lots',json={'produit_id':prod_id,'numero_lot':'AUDIT-2026-09','date_fabrication':'2026-09-01','date_expiration':'2027-09-01','quantite_initiale':50,'quantite_restante':50,'fournisseur':'Audit Lab','date_reception':'2026-09-15','prix_achat_lot':4000}),{200,201})
lot_id=lot.get('lot_id') or lot.get('id'); print('LOT_ID',lot_id)
# Reception flow: create appointment for patient 1 with doctor 4 at a future configured slot.
rdv_time='2026-09-15T13:30:00'
rdv=call('create_rdv',assistant.post(B+'/api/v1/agenda/rdv',json={'patient_id':1,'praticien_id':4,'acte_id':act_id,'date_heure':rdv_time,'salle':'Salle Audit'}),{200,201})
rdv_id=rdv.get('id') or rdv.get('rdv_id'); print('RDV_ID',rdv_id)
arr=call('patient_arrive',assistant.post(B+f'/api/v1/accueil/rdv/{rdv_id}/arrivee'),{200})
# Doctor: sign act consent, create clinical dossier, upload photo, export dossier.
sig=base64.b64encode(b'audit-signature-patient-2026').decode()
cons=call('sign_consent',doctor.post(B+'/api/v1/patients/1/consentements',json={'acte_id':act_id,'signature_base64':sig,'methode_signature':'tactile','type_consentement':'acte_medical'}),{200})
dossier=call('create_dossier',doctor.post(B+'/api/v1/patients/1/dossiers',json={'praticien_id':4,'rdv_id':rdv_id,'acte_id':act_id,'date_acte':'2026-09-15','zones_traitees':{'front':'zone centrale'},'produits_utilises':{'produit_id':prod_id,'lot_id':lot_id,'quantite':2},'observations':'Bonne tolérance. Résultat naturel.','effets_secondaires':'Aucun','satisfaction_patient':5,'suivi_requis':True,'date_suivi_recommandee':'2026-10-15','actes_details':[{'nom':'Audit Botox Clinique','prix':320}]}),{200,201})
dossier_id=dossier.get('dossier_id'); print('DOSSIER_ID',dossier_id)
with open('/home/ubuntu/audit-clinic/qa_photo_avant_fake.jpg','rb') as f:
 photo=call('upload_photo',doctor.post(B+'/api/v1/patients/1/photos',params={'type_photo':'avant','dossier_id':dossier_id,'zone':'front'},files={'file':('audit-photo.jpg',f,'image/jpeg')}),{200,201})
photo_id=photo.get('photo_id'); print('PHOTO_ID',photo_id)
# consume injectable if endpoint accepts this contract
util=doctor.post(B+'/api/v1/injectables/utilisation',json={'lot_id':lot_id,'patient_id':1,'praticien_id':4,'dossier_id':dossier_id,'quantite':2,'unite':'unité','type_injection':'Audit Botox Clinique','notes':'Utilisation pendant recette'}); print('injectable_use',util.status_code,util.text[:300])
# Exports and content checks.
structured=call('export_structured',doctor.get(B+'/api/v1/patients/1/export-structured'),{200}); open(OUT+'/dossier_export.json','w').write(json.dumps(structured,ensure_ascii=False,indent=2)); print('structured_contains_observation', 'Bonne tolérance' in json.dumps(structured,ensure_ascii=False), 'entries',len(structured.get('entries',[])))
pdf=doctor.get(B+'/api/v1/patients/1/export-pdf'); print('dossier_pdf',pdf.status_code,pdf.headers.get('content-type'),len(pdf.content)); open(OUT+'/dossier_export.pdf','wb').write(pdf.content)
# Assistant billing: create invoice linked to dossier, pay, download and validate bytes.
inv=call('create_invoice',assistant.post(B+'/api/v1/factures',json={'patient_id':1,'rdv_id':rdv_id,'dossier_id':dossier_id,'actes':[{'description':'Audit Botox Clinique','prix':320,'quantite':1}],'produits':[],'taux_tva':0,'remise_globale_pct':0,'notes':'Recette multi-rôles'}),{200,201})
inv_id=inv.get('id') or inv.get('facture_id'); print('INVOICE_ID',inv_id)
pay=call('pay_invoice',assistant.post(B+f'/api/v1/factures/{inv_id}/payer',json={'mode_paiement':'carte'}),{200,201})
inv_pdf=assistant.get(B+f'/api/v1/factures/{inv_id}/pdf'); print('invoice_pdf',inv_pdf.status_code,inv_pdf.headers.get('content-type'),len(inv_pdf.content)); open(OUT+'/facture.pdf','wb').write(inv_pdf.content)
print('RESULT_IDS',json.dumps({'acte_id':act_id,'produit_id':prod_id,'lot_id':lot_id,'rdv_id':rdv_id,'dossier_id':dossier_id,'photo_id':photo_id,'facture_id':inv_id}))
