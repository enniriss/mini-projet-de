"""
Génération de CSV de transactions DÉTERMINISTES.

Format :
datetime_transaction, iban_origine, pays_source, banque_source,
iban_destinataire, pays_destinataire, montant

L'option --inject-bug permet de simuler une erreur
pour tester la robustesse de la pipeline.
"""

import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

COLUMNS = [
    "datetime_transaction",
    "iban_origine",
    "pays_source",
    "banque_source",
    "iban_destinataire",
    "pays_destinataire",
    "montant"
]

# Jeu de données fixe : (iban_o, pays_o, banque, iban_d, pays_d, montant)

FILE_1 = [
    ("FR7630006000011234567890189", "FR", "BNP", "DE89370400440532013000", "DE", "100.00"),
    ("FR7630006000011234567890189", "FR", "BNP", "ES9121000418450200051332", "ES", "250.50"),
    ("DE89370400440532013000", "DE", "COMMERZBANK", "FR7630006000011234567890189", "FR", "5000.00"),
    ("DE89370400440532013000", "DE", "COMMERZBANK", "IT60X0542811101000000123456", "IT", "5000.01"),
    ("ES9121000418450200051332", "ES", "SANTANDER", "FR7630006000011234567890189", "FR", "75.25"),
    ("IT60X0542811101000000123456", "IT", "UNICREDIT", "DE89370400440532013000", "DE", "12000.00"),
]

FILE_2 = [
    ("FR7630006000011234567890189", "FR", "BNP", "IT60X0542811101000000123456", "IT", "10.00"),
    ("ES9121000418450200051332", "ES", "SANTANDER", "DE89370400440532013000", "DE", "4999.99"),
    ("IT60X0542811101000000123456", "IT", "UNICREDIT", "FR7630006000011234567890189", "FR", "300.00"),
    ("DE89370400440532013000", "DE", "COMMERZBANK", "ES9121000418450200051332", "ES", "6000.00"),
    ("FR7630006000011234567890189", "FR", "BNP", "DE89370400440532013000", "DE", "0.01"),
]

DATASETS = {
    "transactions_001.csv": FILE_1,
    "transactions_002.csv": FILE_2
}

START = datetime(2026, 1, 1, 9, 0, 0)


def build_rows(dataset, inject_bug=False):
    """Construire les lignes du CSV."""

    rows = []

    for i, (io, po, bank, idst, pd_, amount) in enumerate(dataset):


        rows.append([
            (START + timedelta(hours=i)).isoformat(),
            io,
            po,
            bank,
            idst,
            pd_,
            amount
        ])


    return rows


def generate(out_dir, inject_bug=False):
    """Générer les fichiers CSV."""

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    paths = []

    for name, dataset in DATASETS.items():
        path = out / name

        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(COLUMNS)
            writer.writerows(build_rows(dataset, inject_bug))

        paths.append(path)

    return paths

if __name__ == "__main__":
    try:
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        inject_bug = "--inject-bug" in sys.argv

        PROJECT_DIR = Path(__file__).resolve().parent.parent
        # Dossier de sortie : 1er argument positionnel, sinon ./data
        out_dir = Path(args[0]) if args else PROJECT_DIR / "data"

        if inject_bug:
            print("[TEST] Injection d'un montant invalide.")

        for path in generate(out_dir, inject_bug=inject_bug):
            print(f"généré : {path}")

        print("Génération terminée avec succès.")

    except (OSError, csv.Error, ValueError) as error:
        print(f"[ERREUR GENERATION] {error}", file=sys.stderr)
        sys.exit(1)