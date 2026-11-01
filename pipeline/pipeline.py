
import subprocess
import time
import tempfile
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

SCRIPT_DIR = PROJECT_DIR / "script"


def run_step(name, command):
    print(f"\n========== {name} ==========")

    subprocess.run(
        command,
        cwd=PROJECT_DIR,
        check=True
    )

    print(f"[OK] {name}")


def wait_for_s3(max_attempts=30, delay=2):
    from script.s3_storage import get_s3_client

    s3 = get_s3_client()

    print("\n[S3] Attente du démarrage du service S3...")

    for attempt in range(1, max_attempts + 1):
        try:
            s3.list_buckets()
            print("[S3] Service S3 opérationnel.")
            return

        except Exception as error:
            print(
                f"[S3] Service indisponible "
                f"({attempt}/{max_attempts}) : {error}"
            )

            if attempt < max_attempts:
                time.sleep(delay)

    raise RuntimeError("Impossible de démarrer le service S3.")


def run_pipeline(inject_bug=False):

    print("\n========== PIPELINE START ==========\n")

    try:
        # ETAPE 1 : Démarrage du service S3
        run_step(
            "1/4 - DEMARRAGE DU SERVICE S3",
            [
                "docker",
                "compose",
                "up",
                "-d",
                "minio"
            ]
        )

        wait_for_s3()

        # ETAPE 2 : Création du bucket
        from script.s3_storage import create_bucket

        create_bucket()

        # ETAPE 3 : Génération temporaire et upload des CSV
        print("\n========== 2/4 - GENERATION ET UPLOAD CSV ==========")

        with tempfile.TemporaryDirectory(
            prefix="pipeline_csv_"
        ) as temp_dir:

            temp_path = Path(temp_dir)

            # Génération des CSV dans le dossier temporaire
            run_step(
                "GENERATION CSV",
                [
                    sys.executable,
                    str(SCRIPT_DIR / "generate_datas.py"),
                    str(temp_path)
                ] + (
                    ["--inject-bug"] if inject_bug else []
                )
            )

            # Vérification des fichiers générés
            csv_files = list(temp_path.glob("*.csv"))

            print(
                f"[PIPELINE] {len(csv_files)} fichier(s) "
                "CSV généré(s)."
            )

            if not csv_files:
                raise RuntimeError(
                    f"Aucun CSV généré dans {temp_path}. "
                    "Vérifie generate_datas.py."
                )

            # Envoi vers le bucket S3
            from script.s3_storage import upload_csv_files

            uploaded = upload_csv_files(temp_path)

            if len(uploaded) != len(csv_files):
                raise RuntimeError(
                    "Tous les fichiers CSV n'ont pas été envoyés vers S3."
                )

            print(
                f"[S3] {len(uploaded)} fichier(s) "
                "envoyé(s) avec succès."
            )

        # Le dossier temporaire est supprimé automatiquement ici.

        # ETAPE 4 : Création de la base SQLite
        run_step(
            "3/4 - CREATION DATABASE",
            [
                sys.executable,
                "-c",
                "from script.database import create_database; "
                "create_database()"
            ]
        )

        # ETAPE 5 : Traitement des fichiers depuis S3
        run_step(
            "4/4 - TRAITEMENT DEPUIS S3 ET INSERTION SQLITE",
            [
                sys.executable,
                "-m",
                "script.lib.loads"
            ]
        )

        print("\n========== PIPELINE SUCCESS ==========")

    except subprocess.CalledProcessError as error:
        print(f"\n[ERREUR] Étape interrompue : {error}")
        print("\n========== PIPELINE FAILED ==========")
        sys.exit(1)

    except Exception as error:
        print(f"\n[ERREUR] {error}")
        print("\n========== PIPELINE FAILED ==========")
        sys.exit(1)


if __name__ == "__main__":
    run_pipeline(inject_bug=False)
