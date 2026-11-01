
import boto3
import time

from pathlib import Path
from botocore.exceptions import ClientError, BotoCoreError


S3_ENDPOINT = "http://localhost:9000"

ACCESS_KEY = "admin"
SECRET_KEY = "minio_password_123"

BUCKET_NAME = "bank-transactions"


def get_s3_client():

    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="us-east-1"
    )


def create_bucket():

    s3 = get_s3_client()

    buckets = s3.list_buckets()["Buckets"]

    if not any(b["Name"] == BUCKET_NAME for b in buckets):

        s3.create_bucket(Bucket=BUCKET_NAME)

        print(f"[S3] Bucket créé : {BUCKET_NAME}")

    else:
        print(f"[S3] Bucket existant : {BUCKET_NAME}")


def upload_csv_files(directory):

    s3 = get_s3_client()

    directory = Path(directory)

    uploaded_files = []

    for file_path in directory.glob("*.csv"):

        s3.upload_file(
            str(file_path),
            BUCKET_NAME,
            file_path.name
        )

        uploaded_files.append(file_path.name)

        print(f"[S3] Fichier envoyé : {file_path.name}")

    return uploaded_files


def list_csv_files():

    s3 = get_s3_client()

    response = s3.list_objects_v2(
        Bucket=BUCKET_NAME
    )

    files = [
        item["Key"]
        for item in response.get("Contents", [])
        if item["Key"].endswith(".csv")
    ]

    return files


def download_csv_with_retry(
    file_key,
    max_attempts=3,
    delay=2
):

    s3 = get_s3_client()

    for attempt in range(1, max_attempts + 1):

        try:

            print(
                f"[S3] Téléchargement de {file_key} "
                f"(tentative {attempt}/{max_attempts})"
            )

            response = s3.get_object(
                Bucket=BUCKET_NAME,
                Key=file_key
            )

            content = response["Body"].read()

            print(f"[S3] Téléchargement réussi : {file_key}")

            return content

        except (ClientError, BotoCoreError, OSError) as error:

            print(f"[S3 ERROR] {error}")

            if attempt < max_attempts:

                print(
                    f"[S3 RETRY] Nouvelle tentative "
                    f"dans {delay} secondes..."
                )

                time.sleep(delay)

            else:

                print(
                    f"[S3 FATAL] Impossible de récupérer {file_key}"
                )

                raise
