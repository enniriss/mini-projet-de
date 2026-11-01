import sqlite3
from pathlib import Path

import pytest

from script.generate_datas import generate, COLUMNS
from script.database import create_database, insert_data


def test_integration_database(tmp_path, monkeypatch):
    # 1. Préparer un dossier temporaire
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    db_path = tmp_path / "test.db"

    # 2. Rediriger la base vers le fichier temporaire
    monkeypatch.setattr("script.database.DB_PATH", db_path)

    # 3. Générer les fichiers CSV
    generate(data_dir)

    # 4. Créer la base de données
    create_database()

    # 5. Lire les fichiers CSV
    import csv

    expected_rows = []

    for csv_file in sorted(data_dir.glob("*.csv")):
        with open(csv_file, "r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)

            for row in reader:
                expected_rows.append(tuple(row[column] for column in COLUMNS))

    # 6. Insérer les données
    insert_data(expected_rows)

    # 7. Vérifier le contenu réel de la base
    conn = sqlite3.connect(db_path)

    try:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM transactions")
        count = cursor.fetchone()[0]

        assert count == len(expected_rows), (
            f"Nombre de lignes incorrect : {count} au lieu de {len(expected_rows)}"
        )

        cursor.execute(
            f"SELECT {', '.join(f'\"{column}\"' for column in COLUMNS)} "
            "FROM transactions ORDER BY id"
        )

        actual_rows = cursor.fetchall()

        assert actual_rows == expected_rows, (
            "Les données présentes dans la base ne correspondent pas aux données attendues."
        )

    finally:
        conn.close()