
import pandas as pd
from io import BytesIO

from ..generate_datas import COLUMNS

from script.s3_storage import (
    download_csv_with_retry,
    list_csv_files
)

from script.database import (
    insert_data,
    get_unprocessed_files
)


def load_transactions(file_path):
    """
    Récupère un CSV depuis S3 et retourne un DataFrame.
    """

    content = download_csv_with_retry(file_path)

    df = pd.read_csv(
        BytesIO(content),
        usecols=COLUMNS
    )

    df['datetime_transaction'] = pd.to_datetime(
        df['datetime_transaction']
    )

    print(f"[LOAD] Fichier chargé depuis S3 : {file_path}")

    return df


def load_multiple_transactions(file_paths):
    """
    Charge plusieurs CSV depuis S3 et les combine.
    """

    dataframes = []

    for file_path in file_paths:
        df = load_transactions(file_path)
        dataframes.append(df)

    combined_df = pd.concat(
        dataframes,
        ignore_index=True
    )

    return combined_df


def sum_transactions_send_by_iban(df):

    df['montant'] = pd.to_numeric(
        df['montant'], errors='raise'
    )

    return (
        df.groupby('iban_origine')['montant']
        .sum()
        .reset_index()
    )


def sum_transactions_send_by_bank(df):

    df['montant'] = pd.to_numeric(
        df['montant'], errors='raise'
    )

    return (
        df.groupby('banque_source')['montant']
        .sum()
        .reset_index()
    )


def sum_transactions_received_by_iban(df):

    df['montant'] = pd.to_numeric(
        df['montant'], errors='raise'
    )

    return (
        df.groupby('iban_destinataire')['montant']
        .sum()
        .reset_index()
    )


def flag_amounts_above_5000(df):

    df['montant'] = pd.to_numeric(
        df['montant'], errors='raise'
    )

    df['flag_above_5000'] = df['montant'] > 5000

    return df


if __name__ == "__main__":

    print("\n========== RECUPERATION DES FICHIERS S3 ==========")

    # Récupérer la liste des CSV présents dans MinIO
    file_paths = list_csv_files()

    if not file_paths:
        print("[S3] Aucun fichier CSV disponible.")
        raise SystemExit(1)

    # Vérifier les fichiers déjà traités
    files_to_process = get_unprocessed_files(file_paths)

    if not files_to_process:

        print("[DATABASE] Tous les fichiers ont déjà été traités.")

    else:

        print(
            f"[LOAD] {len(files_to_process)} fichier(s) "
            "à récupérer depuis S3."
        )

        # Chargement des CSV depuis S3
        df = load_multiple_transactions(files_to_process)

        # Calculs
        print("\nSomme des transactions envoyées par IBAN:")
        print(sum_transactions_send_by_iban(df))

        print("\nSomme des transactions envoyées par banque:")
        print(sum_transactions_send_by_bank(df))

        print("\nSomme des transactions reçues par IBAN:")
        print(sum_transactions_received_by_iban(df))

        print("\nTransactions avec flag pour montants supérieurs à 5000:")
        print(flag_amounts_above_5000(df))

        # Conversion des dates pour SQLite
        df['datetime_transaction'] = (
            df['datetime_transaction'].dt.strftime(
                '%Y-%m-%d %H:%M:%S'
            )
        )

        data = df[COLUMNS].itertuples(
            index=False,
            name=None
        )

        # Insertion en base avec retry
        print("\n========== INSERTION DATABASE ==========")

        insert_data(
            data,
            file_paths=files_to_process,
            inject_bug=False
        )
