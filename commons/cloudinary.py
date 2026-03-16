import cloudinary
from cloudinary import uploader
from commons.timeit import timeit
from logging import getLogger

logger = getLogger(__name__)
          
cloudinary.config( 
  cloud_name = "dtbl4jg02", 
  api_key = "313873736982566", 
  api_secret = "uhb8rZ5Tv8pca_VY29pdhR63caI" 
)

@timeit
def upload_image(image, resource_type="image"):
    """
    Upload image to cloudinary
    """
    try:
        res = uploader.upload(image, resource_type=resource_type)
        return res
    except Exception as e:
        logger.error(f"Error in uploading image to cloudinary {e}")
        raise e