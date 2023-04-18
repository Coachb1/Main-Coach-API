import boto3
from botocore.config import Config

from commons.timeit import timeit


@timeit
def get_url(bucket, key):
    s3 = boto3.client('s3', config=Config(signature_version='s3v4'))

    return s3.generate_presigned_url(
        ClientMethod='get_object',
        Params={
            'Bucket': bucket,
            'Key': key
        },
        ExpiresIn=15*60
    )
