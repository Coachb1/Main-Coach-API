import os
import base64
from pathlib import Path


class GCPServiceAccountFile:
    """
    Ensures a GCP service account JSON file exists locally.
    Decodes Base64 credentials from env and writes them to /tmp.
    """

    ENV_KEY = "GCP_SERVICE_ACCOUNT_BASE64"
    DIR_PATH = Path("/tmp/app_secrets")
    FILE_NAME = "gcp_service_account.json"

    def __init__(self):
        self.file_path = self.DIR_PATH / self.FILE_NAME

    def get_path(self) -> str:
        """
        Returns the path to the service account JSON file.
        Creates it if it doesn't exist.
        """

        # If file already exists, return it
        if self.file_path.exists():
            return str(self.file_path)

        base64_creds = os.getenv(self.ENV_KEY)

        if not base64_creds:
            raise ValueError(f"{self.ENV_KEY} not found in environment variables")

        # Ensure directory exists
        self.DIR_PATH.mkdir(parents=True, exist_ok=True)

        # Decode base64 credentials
        decoded_creds = base64.b64decode(base64_creds)

        # Write JSON file
        with open(self.file_path, "wb") as f:
            f.write(decoded_creds)

        # Secure file permissions (owner read/write only)
        os.chmod(self.file_path, 0o600)

        return str(self.file_path)