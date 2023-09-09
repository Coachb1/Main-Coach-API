import logging

import boto3

from commons.timeit import timeit
from google.cloud import storage
import io


logger = logging.getLogger(__name__)


@timeit
def s3_upload(file,
              bucket_name: str,
              s3_file_name: str,
              region_name: str):
    logger.info("trying s3_upload %s", s3_file_name)
    session = boto3.session.Session()
    s3 = session.client('s3', region_name=region_name)
    s3.upload_fileobj(file, bucket_name, s3_file_name)
    logger.info("success s3_upload %s", s3_file_name)


@timeit
def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    try:

        client = storage.Client.from_service_account_json(r'C:\Users\Hello\gcp\bucketaccess.json')
        # storage_client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        generation_match_precondition = 0
        
        blob.upload_from_string(source_file_name.read(), content_type=source_file_name.content_type , if_generation_match=generation_match_precondition)

        print(
            f"File {source_file_name} uploaded to {destination_blob_name}."
        )
    except Exception as error: 
        print(f"Error uploading file {source_file_name} due to {str(error)}")
        raise error