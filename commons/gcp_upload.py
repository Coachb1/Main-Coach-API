
import logging


from commons.gcp_service import GCPServiceAccountFile
from commons.timeit import timeit
from google.cloud import storage
import os
from pathlib import Path

logger = logging.getLogger(__name__)

gcp_service_acccount = GCPServiceAccountFile()


@timeit
def gcp_upload(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    try:
        os.chdir(f"{Path(__file__).resolve().parent}")
        client = storage.Client.from_service_account_json(gcp_service_acccount.get_path())
        # client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        generation_match_precondition = 0
        
        blob.upload_from_string(source_file_name.read(), content_type=source_file_name.content_type , if_generation_match=generation_match_precondition)

        logger.info(
            f"File {source_file_name} uploaded to {destination_blob_name}."
        )
    except Exception as error: 
        logger.error(f"Error uploading file {source_file_name} due to {str(error)}")