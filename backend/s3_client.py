"""
KisanMitra — backend/s3_client.py
Unified AWS S3 Client for syncing agronomy guides, mandi prices,
and storing crop diagnostic images with offline local fallback.
"""

import io
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("kisanmitra.s3")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "kisanmitra-data-2026")
REGION = os.environ.get("AWS_REGION", "eu-north-1")

_s3_client = None

def get_s3_client():
    global _s3_client
    if _s3_client is not None:
        return _s3_client
    ak = os.environ.get("AWS_ACCESS_KEY_ID")
    sk = os.environ.get("AWS_SECRET_ACCESS_KEY")
    if not ak or not sk:
        logger.info("AWS credentials not configured in environment; S3 client disabled.")
        return None
    try:
        _s3_client = boto3.client(
            "s3",
            region_name=REGION,
            aws_access_key_id=ak,
            aws_secret_access_key=sk
        )
        return _s3_client
    except Exception as e:
        logger.warning(f"Failed to initialize S3 client: {e}")
        return None

def check_s3_connection() -> Dict[str, Any]:
    """Tests connectivity to AWS S3 and the specific project bucket."""
    client = get_s3_client()
    if not client:
        return {
            "connected": False,
            "bucket": BUCKET_NAME,
            "reason": "Missing AWS credentials"
        }
    try:
        client.head_bucket(Bucket=BUCKET_NAME)
        # Count objects
        res = client.list_objects_v2(Bucket=BUCKET_NAME, MaxKeys=50)
        obj_count = res.get("KeyCount", 0)
        return {
            "connected": True,
            "bucket": BUCKET_NAME,
            "region": REGION,
            "objects_count": obj_count
        }
    except ClientError as e:
        logger.error(f"S3 connection check failed: {e}")
        return {
            "connected": False,
            "bucket": BUCKET_NAME,
            "error": str(e)
        }

def fetch_s3_guide(crop_name: str) -> Tuple[str, bool]:
    """
    Fetches verified agronomy guide from S3: guides/{crop}.txt
    Falls back to local file or default agronomic guidelines.
    """
    clean_crop = crop_name.strip().lower()
    crop_file_map = {
        "chickpea": "gram",
        "chana": "gram",
        "हरभरा": "gram",
        "चना": "gram",
        "sorghum": "jowar",
        "jawari": "jowar",
        "ज्वारी": "jowar",
        "pyaj": "onion",
        "कांदा": "onion",
        "प्याज": "onion",
        "टमाटर": "tomato",
        "टोमॅटो": "tomato",
        "gehun": "wheat",
        "गहू": "wheat",
        "गेहूं": "wheat"
    }
    file_crop = crop_file_map.get(clean_crop, clean_crop)
    s3_key = f"guides/{file_crop}.txt"

    client = get_s3_client()
    if client:
        try:
            resp = client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
            text = resp["Body"].read().decode("utf-8")
            logger.info(f"Loaded crop guide for {crop_name} from s3://{BUCKET_NAME}/{s3_key}")
            return text, True
        except Exception as e:
            logger.warning(f"Could not load s3://{BUCKET_NAME}/{s3_key}: {e}")

    # Local fallback
    local_path = DATA_DIR / "guides" / f"{file_crop}.txt"
    if local_path.exists():
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                return f.read(), False
        except Exception:
            pass

    return f"Standard ICAR Package of Practices for {crop_name.title()}: Maintain balanced soil moisture, proper spacing, and use Trichoderma seed treatment.", False

def upload_crop_diagnostic_image(image_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> Optional[str]:
    """Uploads farmer's analyzed crop image to S3 for traceability."""
    client = get_s3_client()
    if not client:
        return None
    s3_key = f"diagnostics/{filename}"
    try:
        client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=image_bytes,
            ContentType=content_type
        )
        return f"s3://{BUCKET_NAME}/{s3_key}"
    except Exception as e:
        logger.warning(f"Failed to upload diagnostic image to S3: {e}")
        return None
