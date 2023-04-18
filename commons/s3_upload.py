import boto3


def s3_upload(file,
              bucket_name: str,
              s3_file_name: str):
    s3 = boto3.client('s3')

    s3.upload_fileobj(file, bucket_name, s3_file_name)
