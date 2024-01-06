import logging

import boto3

from commons.timeit import timeit
from google.cloud import storage
import io
import os
from pathlib import Path

logger = logging.getLogger(__name__)


@timeit
def s3_upload(file,
              bucket_name: str,
              s3_file_name: str,
              region_name: str):
    """
    Uploads a file to an S3 bucket using the Boto3 library.

    Args:
        file: The file object to be uploaded to S3.
        bucket_name: The name of the S3 bucket where the file will be uploaded.
        s3_file_name: The desired name of the file in S3.
        region_name: The AWS region where the S3 bucket is located.

    
    """
    logger.info("trying s3_upload %s", s3_file_name)
    session = boto3.session.Session()
    s3 = session.client('s3', region_name=region_name)
    s3.upload_fileobj(file, bucket_name, s3_file_name)
    logger.info("success s3_upload %s", s3_file_name)



