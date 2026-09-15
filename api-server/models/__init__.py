"""Package `models` — enregistrement centralisé des mappers SQLAlchemy.

Correction (revue Bloc 1 v2, 2026-09-09) : ce fichier était vide. Les
modules satellites (`omnicanal`, `security`, `workflow_engine`,
`episode_core`) n'étaient importés explicitement que dans
`alembic/env.py` (pour l'autogénération) et `local_validation_setup.py`
(pour les tests locaux) — jamais au démarrage réel de l'API. Tant qu'un
routeur n'importait pas lui-même l'un de ces modules, ses classes
pouvaient ne pas être enregistrées dans `Base.metadata` avant que
SQLAlchemy ne configure les mappers (notamment les relations
`back_populates` ajoutées dans `models/database.py` vers des classes de
`episode_core.py`, ex. `Facture.lignes`/`Facture.paiements`).

En important tous les modules de modèles ici, tout code qui fait
`from models.database import ...` ou même simplement `import models`
déclenche automatiquement l'exécution de ce fichier (comportement
standard de Python pour un package) — donc les mappers sont toujours
enregistrés avant utilisation, quel que soit le premier routeur chargé.
"""
from models.database import Base  # noqa: F401 — doit être importé en premier (les autres en dépendent)
from models import omnicanal  # noqa: F401
from models import security  # noqa: F401
from models import workflow_engine  # noqa: F401
from models import episode_core  # noqa: F401
