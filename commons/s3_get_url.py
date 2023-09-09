import boto3
from botocore.config import Config

from commons.timeit import timeit
from google.cloud import storage


@timeit
def get_url(region_name, bucket, key,expiration_time):
    # s3 = boto3.client('s3', region_name=region_name, config=Config(signature_version='s3v4'))

    # return s3.generate_presigned_url(
    #     ClientMethod='get_object',
    #     Params={
    #         'Bucket': bucket,
    #         'Key': key
    #     },
    #     ExpiresIn=15*60
    # )
    client = storage.Client.from_service_account_json(r'C:\Users\Hello\gcp\bucketaccess.json')
    # client = storage.Client()
    bucket = client.get_bucket(bucket)
    blob = bucket.blob(key)

    url = blob.generate_signed_url(
        version='v4',
        expiration=expiration_time,
        method='GET'
    )

    return url