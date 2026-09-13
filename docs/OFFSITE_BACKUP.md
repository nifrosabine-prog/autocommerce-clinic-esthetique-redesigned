# Sauvegarde hors-site — AutoCommerce Clinic (mono-VPS)

Synchro miroir par `rsync` + SSH des volumes de données vers une machine
distante (NAS, second VPS, serveur d'archives). Ceci neutralise le point
unique de défaillance du mono-VPS : la perte du serveur ou son vol ne fait
plus perdre les sauvegardes locales ni les photos patients.

## Ce qui est synchronisé

| Volume Docker | Contenu | Cible distante |
|---|---|---|
| `clinic_backups` | dumps `pg_dump` + archives `_data.tar.gz` (produits par `scripts/backup.sh`) | `<cible>/clinic_backups/` |
| `clinic_data` | photos, uploads factures, branding | `<cible>/clinic_data/` |

Le miroir distant reflète exactement l'état local : les fichiers purgés
localement par la rétention (`RETENTION_DAYS`) sont supprimés côté distant
(`rsync --delete`).

## Mise en place

```bash
# 1. Clé SSH (jamais de mot de passe)
ssh-keygen -t ed25519 -f ~/.ssh/autocommerce_offsite -N ''
ssh-copy-id -i ~/.ssh/autocommerce_offsite.pub backup@nas.local

# 2. Config
sudo mkdir -p /etc/autocommerce
sudo install -m 600 deploy/offsite.env.example /etc/autocommerce/offsite.env
sudo nano /etc/autocommerce/offsite.env        # renseigner OFFSITE_TARGET

# 3. Premier essai en dry-run, puis vraie synchronisation
sudo OFFSITE_DRY_RUN=true scripts/offsite_sync.sh
sudo scripts/offsite_sync.sh
ls /volume/autocommerce/clinic_backups        # sur la machine distante
```

## Planification

Cron (tous les jours à 02:30, heure locale) :

```cron
30 2 * * * root /opt/autocommerce/scripts/offsite_sync.sh >> /var/log/autocommerce_offsite_cron.log 2>&1
```

Ou systemd (timer) :

```ini
# /etc/systemd/system/autocommerce-offsite.service
[Unit]
Description=Sauvegarde hors-site AutoCommerce Clinic
After=docker.service

[Service]
Type=oneshot
ExecStart=/opt/autocommerce/scripts/offsite_sync.sh

# /etc/systemd/system/autocommerce-offsite.timer
[Unit]
Description=Horaire sauvegarde hors-site AutoCommerce Clinic

[Timer]
OnCalendar=*-*-* 02:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now autocommerce-offsite.timer
systemctl list-timers autocommerce-offsite.timer
```

## Surveillance

- Journal : `/var/log/autocommerce_offsite.log` (rotation à 20 Mo) ;
  chaque volume journalise `rsync exit=$rc` (`0` = OK, `24` = toléré).
- En cas d'échec : code de sortie non nul + alerte webhook si
  `OFFSITE_WEBHOOK_URL` est renseigné.
- Drill recommandé mensuel : `ssh backup@nas.local du -sh /volume/autocommerce/*`
  puis restaurer réellement sur un VPS d'entraînement (voir restauration).

## Restauration depuis la copie hors-site

1. Rapatrier un dump + son archive de données depuis le distant :
   ```bash
   scp -i ~/.ssh/autocommerce_offsite \
     backup@nas.local:/volume/autocommerce/clinic_backups/clinic_production_*.dump .
   scp -i ~/.ssh/autocommerce_offsite \
     backup@nas.local:/volume/autocommerce/clinic_backups/clinic_production_*_data.tar.gz .
   ```
2. Déposer les fichiers dans le volume `clinic_backups` du VPS :
   ```bash
   VOL=$(docker volume inspect --format '{{.Mountpoint}}' clinic_backups)
   sudo cp clinic_production_*.dump "$VOL"/
   sudo cp clinic_production_*_data.tar.gz "$VOL"/
   ```
3. Appliquer la restauration standard (base + données) :
   ```bash
   docker compose -f docker-compose.production.yml --env-file deploy/production.env stop api worker beat
   docker compose -f docker-compose.production.yml --env-file deploy/production.env \
     exec -T backup sh /scripts/restore.sh <dump> <archive_donnees.tar.gz>
   docker compose -f docker-compose.production.yml start api worker beat
   ```
   (voir scripts/restore.sh : arrêt préalable des services écrivants, vidage
   de `/data` si copie exacte requise.)

## Sécurité

- Authentification **par clé uniquement**, clé dédiée `autocommerce_offsite`
  (restreindre côté distant : `command=` dans `~backup/.ssh/authorized_keys`
  pour limiter à `rsync --server`).
- Config de secrets en `chmod 600` (`/etc/autocommerce/offsite.env`), jamais
  committée ni livrée.
- Chiffrement au repos côté distant recommandé (disque chiffré / snapshots ZFS).
