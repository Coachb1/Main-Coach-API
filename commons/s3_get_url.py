import boto3

from commons.timeit import timeit


@timeit
def get_url(bucket, key):
    s3_obj = boto3.resource('s3').Object(bucket, key)
    return s3_obj.meta.client.generate_presigned_url('get_object', ExpiresIn=10 * 60,
                                                     Params={'Bucket': bucket, 'Key': key})
