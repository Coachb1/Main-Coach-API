import boto3
from botocore.config import Config

from commons.gcp_service import GCPServiceAccountFile
from commons.timeit import timeit
from google.cloud import storage
import os
from pathlib import Path

gcp_service_acccount = GCPServiceAccountFile()


@timeit
def get_url(region_name, bucket, key, public_url=False):
    """
    Generates a signed URL for accessing a file in a Google Cloud Storage bucket.

    Args:
        region_name (str): A string representing the region where the bucket is located.
        bucket (str): A string representing the name of the Google Cloud Storage bucket.
        key (str): A string representing the path to the file in the bucket.

    Returns:
        str: A signed URL that can be used to access the file in the Google Cloud Storage bucket.
    """

    # s3 = boto3.client('s3', region_name=region_name, config=Config(signature_version='s3v4'))

    # return s3.generate_presigned_url(
    #     ClientMethod='get_object',
    #     Params={
    #         'Bucket': bucket,
    #         'Key': key
    #     },
    #     ExpiresIn=15*60
    # )
    os.chdir(f"{Path(__file__).resolve().parent}")
    client = storage.Client.from_service_account_json(gcp_service_acccount.get_path())
    bucket = client.get_bucket(bucket)
    blob = bucket.blob(key)

    if public_url:
        return blob.public_url

    url = blob.generate_signed_url(
        version='v4',
        expiration=15*60,
        method='GET'
    )

    return url