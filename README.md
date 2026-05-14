# Big Data News Analytics Platform

Plateforme complète d'ingestion, transformation et visualisation de données de presse, basée sur une stack Big Data conteneurisée (Kafka, MinIO, Airflow, PostgreSQL, Superset).

---

## Prérequis

Avant de commencer, assurez-vous d'avoir installé :

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Git](https://git-scm.com/)
- Python 3.9+ *(optionnel, pour les scripts locaux)*

---

## Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/ghita61/Projet_Architecture_de_donn-es.git
cd Projet_Architecture_de_donn-es
```

### 2. Créer le fichier `.env`

Créez un fichier `.env` à la racine du projet avec le contenu suivant :

```env
# MinIO
MINIO_ROOT_USER=minio_admin
MINIO_ROOT_PASSWORD=ghitaaya
MINIO_PORT=9000
MINIO_CONSOLE_PORT=9001

# PostgreSQL Warehouse
POSTGRES_USER=warehouse_user
POSTGRES_PASSWORD=ghitaaya
POSTGRES_DB=news_warehouse
POSTGRES_PORT=5432

# Airflow
AIRFLOW_PORT=8080

# Superset
SUPERSET_SECRET_KEY=ghitaaya
SUPERSET_PORT=8088
```

> ⚠️ Ne jamais commiter ce fichier sur GitHub. Il est listé dans `.gitignore`.

### 3. Lancer tous les services

```bash
docker-compose up -d
```

La première exécution prend ~5–10 minutes le temps de télécharger les images Docker.

### 4. Vérifier que tout tourne

```bash
docker-compose ps
```

Tous les services doivent afficher `Up` ou `healthy`.

---

## Accès aux interfaces

| Service | URL | Identifiants |
|---|---|---|
| Kafka UI | http://localhost:8081 | pas d'authentification |
| MinIO Console | http://localhost:9001 | `minio_admin` / `ghitaaya` |
| Airflow | http://localhost:8080 | `admin` / `ghitaaya` |
| Superset | http://localhost:8088 | `admin` / `ghitaaya` |

---

## Utilisation

### Lancer un pipeline Airflow

1. Ouvrez Airflow sur http://localhost:8080
2. Allez dans l'onglet **DAGs**
3. Activez le DAG souhaité (toggle à gauche)
4. Cliquez **Trigger DAG** pour lancer manuellement

### Vérifier les données dans MinIO

Les buckets correspondent aux couches de la data lake :

| Bucket | Rôle |
|---|---|
| `bronze` | Données brutes ingérées |
| `silver` | Données nettoyées et transformées |
| `gold` | Données agrégées prêtes à l'analyse |
| `quality-reports` | Rapports de qualité des données |
| `quarantine` | Données rejetées |

### Connecter Superset à PostgreSQL

Dans Superset : `Settings → Database Connections → + Database`, puis utilisez la chaîne de connexion :

```
postgresql://warehouse_user:ghitaaya@postgres:5432/news_warehouse
```

---

## Architecture

```
Kafka (streaming)
    │
    ▼
Airflow DAGs (orchestration)
    │
    ├──► MinIO (data lake — bronze / silver / gold)
    │
    └──► PostgreSQL (data warehouse)
              │
              ▼
           Superset (dashboards)
```

---

## Commandes utiles

```bash
# Arrêter tous les services
docker-compose down

# Voir les logs d'un service en temps réel
docker-compose logs -f airflow-webserver

# Redémarrer un service spécifique
docker-compose restart minio

# Statut détaillé de tous les conteneurs
docker-compose ps

# Reset complet — supprime tous les volumes et données !
docker-compose down -v && docker-compose up -d
```

---

## Structure du projet

```
.
├── airflow/
│   └── dags/          # DAGs Airflow
├── scrapers/          # Scripts de scraping
├── pipelines/         # Logique de transformation
├── ingestion/         # Scripts d'ingestion Kafka
├── quality/           # Contrôles qualité des données
├── governance/        # Règles de gouvernance
├── warehouse/
│   └── init.sql       # Schéma initial PostgreSQL
├── docker-compose.yml
├── .env               # Variables d'environnement (non commité)
└── README.md
```

---

## ⚠️ Points d'attention

- **Ne jamais commiter `.env`** — il contient les mots de passe. Vérifiez que `.gitignore` le liste bien.
- **`docker-compose down -v`** supprime toutes les données des volumes (MinIO, PostgreSQL, Airflow). À n'utiliser qu'en cas de reset complet voulu.
- Le mot de passe Airflow DB est hardcodé dans `docker-compose.yml` — toute modification nécessite un `down -v` suivi d'un `up -d`.
