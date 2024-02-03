import boto3

s3 = boto3.client(endpoint_url="https://s3.de.io.cloud.ovh.net/", aws_access_key_id="6c8abbad51fe4ead8e6f6ce4cb91175c", aws_secret_access_key="a5a2bbf0a9a2470ea9e6b50a1cf38cc6", service_name="s3",
                    region_name="de")

def upload_to_ovh_s3(file, s3_file_name):
    s3.upload_fileobj(file, "coachbot", s3_file_name)



def get_ovh_url(file_name):
    """
    Generates a pre-signed URL for accessing a file in an S3 bucket.

    Args:
        file_name (str): The name of the file for which the pre-signed URL is generated.

    Returns:
        str: The pre-signed URL for accessing the specified file in the S3 bucket.
    """
    return s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': "coachbot",
                'Key': file_name
            },
            ExpiresIn=15*60
        )
