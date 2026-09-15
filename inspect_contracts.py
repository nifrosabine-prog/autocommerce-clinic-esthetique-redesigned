import json, requests
s=requests.get('http://127.0.0.1:8000/openapi.json').json()
paths=['/api/v1/settings/actes','/api/v1/equipe/membres','/api/v1/injectables/produits','/api/v1/injectables/lots','/api/v1/agenda/rdv','/api/v1/accueil/rdv/{rdv_id}/arrivee','/api/v1/patients/{patient_id}/consentements','/api/v1/patients/{patient_id}/dossiers','/api/v1/patients/{patient_id}/medical-facts','/api/v1/patients/{patient_id}/photos','/api/v1/factures','/api/v1/factures/{facture_id}/paiements','/api/v1/factures/{facture_id}/payer']
for p in paths:
 print('\n###',p)
 print(json.dumps(s['paths'].get(p,{}),ensure_ascii=False,indent=2)[:14000])
print('\n### schemas')
for k,v in s['components']['schemas'].items():
 if any(x in k.lower() for x in ['acte','rdv','arrival','arrive','consent','facture','paiement','inject','lot','produit','dossier','medicalfact','medical_fact']): print(k,json.dumps(v,ensure_ascii=False))
