import asyncio
import logging

import aiobotocore

from commons.timeit import timeit

logger = logging.getLogger(__name__)


async def s3_upload_async(file, bucket_name, s3_file_name):
    """
        Upload a file to Amazon S3 using asynchronous programming.

        Parameters:
            file (str): The path of the file to be uploaded.
            bucket_name (str): The name of the S3 bucket.
            s3_file_name (str): The desired S3 file name.

        Returns:
            Union[None, dict]: The response from S3 if the upload is successful, None otherwise.

    """
    async with aiobotocore.get_session().create_client("s3") as s3:
        chunk_size = 5 * 1024 * 1024
        try:
            with open(file, "rb") as f:
                response = await s3.upload_fileobj(f, bucket_name, s3_file_name,
                                                   ExtraArgs={"ContentType": "application/octet-stream"},
                                                   Config=aiobotocore.config.UploadConfig(max_concurrency=10,
                                                                                          multipart_threshold=chunk_size,
                                                                                          multipart_chunksize=chunk_size))
            logger.info(f"Uploaded {file} to {bucket_name}/{s3_file_name}")
            return response
        except Exception as e:
            logger.error(f"Error uploading {file} to S3: {e}")
            raise e


@timeit
def s3_upload(file, bucket_name, s3_file_name) -> None:
    # Creating another thread to execute function

    try:
        loop = asyncio.get_event_loop()
    except:
        loop = asyncio.new_event_loop()

    asyncio.set_event_loop(loop)
    loop.run_until_complete(s3_upload_async(file, bucket_name, s3_file_name))
    loop.close()
