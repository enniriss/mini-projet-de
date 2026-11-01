
import sqlite3
import time
from pathlib import Path

from script.generate_datas import COLUMNS
from script.s3_storage import get_s3_client, BUCKET_NAME

import hashlib

from script.s3_storage import (
    get_s3_client,
    BUCKET_NAME
)

PROJECT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_DIR / "data" / "bank.db"


def create_database():
    """Créer la base de données et les tables."""

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    try:
        columns_sql = ", ".join(
            f'"{column}" TEXT NOT NULL'
            for column in COLUMNS
        )

        query = f"""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {columns_sql},
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """

        conn.execute(query)

        # Table de suivi des fichiers CSV traités
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_files (
                file_id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()

        print(f"[DATABASE] Base créée : {DB_PATH}")

    finally:
        conn.close()


def get_file_hash(file_path):
    """Identifier un fichier S3 par son nom et son ETag."""

    s3 = get_s3_client()

    metadata = s3.head_object(
        Bucket=BUCKET_NAME,
        Key=file_path
    )

    etag = metadata["ETag"].strip('"')

    return hashlib.sha256(
        f"{file_path}:{etag}".encode()
    ).hexdigest()


def get_unprocessed_files(file_paths):
    """Retourner uniquement les fichiers qui ne sont pas encore traités."""

    conn = sqlite3.connect(DB_PATH)

    try:
        unprocessed = []

        for file_path in file_paths:

            file_id = get_file_hash(file_path)

            existing = conn.execute(
                """
                SELECT 1
                FROM processed_files
                WHERE file_id = ?
                """,
                (file_id,)
            ).fetchone()

            if existing:
                print(
                    f"[SKIP] Fichier déjà traité : "
                    f"{Path(file_path).name}"
                )
            else:
                unprocessed.append(file_path)

        return unprocessed

    finally:
        conn.close()


def insert_data(data, file_paths, inject_bug=False,
                max_attempts=3, delay=2):
    """
    Insérer les transactions et enregistrer les fichiers traités.
    Le retry réutilise les données déjà chargées en mémoire.
    """

    data = list(data)
    file_paths = list(file_paths)

    if not file_paths:
        print("[DATABASE] Aucun nouveau fichier à traiter.")
        return

    if not data:
        print("[DATABASE] Aucune donnée à insérer.")
        return

    # Calculer les identifiants avant les tentatives
    files = [
        (get_file_hash(path), str(Path(path).resolve()))
        for path in file_paths
    ]

    for attempt in range(1, max_attempts + 1):

        conn = sqlite3.connect(DB_PATH)

        try:
            print(
                f"\n[INSERTION] Tentative "
                f"{attempt}/{max_attempts}"
            )

            # Verrouiller et démarrer une transaction
            conn.execute("BEGIN IMMEDIATE")

            existing_ids = {
                row[0]
                for row in conn.execute(
                    "SELECT file_id FROM processed_files"
                ).fetchall()
            }

            already_processed = [
                path for file_id, path in files
                if file_id in existing_ids
            ]

            if already_processed:
                if len(already_processed) == len(files):
                    conn.commit()
                    print(
                        "[SKIP] Tous les fichiers sont déjà traités."
                    )
                    return

                raise sqlite3.IntegrityError(
                    "Certains fichiers de ce lot ont déjà été traités. "
                    "Relancez le traitement avec uniquement les fichiers "
                    "non traités."
                )

            columns = ", ".join(
                f'"{column}"' for column in COLUMNS
            )

            placeholders = ", ".join(
                "?" for _ in COLUMNS
            )

            query = f"""
                INSERT INTO transactions ({columns})
                VALUES ({placeholders})
            """

            # Insertion des transactions
            conn.executemany(query, data)

            # Simulation d'une erreur après l'insertion,
            # mais avant la validation de la transaction
            if inject_bug and attempt == 1:
                raise sqlite3.OperationalError(
                    "BUG VOLONTAIRE : erreur temporaire SQLite"
                )

            # Enregistrer tous les fichiers du lot
            conn.executemany(
                """
                INSERT INTO processed_files (file_id, file_path)
                VALUES (?, ?)
                """,
                files
            )

            # Valider les transactions ET les fichiers ensemble
            conn.commit()

            print(
                f"[DATABASE] {len(data)} transactions insérées."
            )
            print(
                f"[DATABASE] {len(files)} fichiers enregistrés."
            )
            print("[OK] Insertion réussie.")

            return

        except sqlite3.Error as error:

            conn.rollback()

            print(f"[ERREUR] Échec de l'insertion : {error}")

            if attempt < max_attempts:

                print(
                    f"[RETRY] Nouvelle tentative dans {delay} secondes..."
                )

                time.sleep(delay)

            else:

                print(
                    "[FATAL] Nombre maximal de tentatives atteint."
                )

                raise

        finally:
            conn.close()


def get_file_hash(file_path):

    s3 = get_s3_client()

    metadata = s3.head_object(
        Bucket=BUCKET_NAME,
        Key=file_path
    )

    etag = metadata["ETag"].strip('"')

    return hashlib.sha256(
        f"{file_path}:{etag}".encode()
    ).hexdigest()