import os
import json
import logging
from datetime import datetime, timezone

import boto3

logger = logging.getLogger("quality_report")


class QualityReporter:

    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
            aws_access_key_id=os.getenv("MINIO_ROOT_USER", "minio_admin"),
            aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "anaskaelar"),
        )

    def save_report(self, summary: dict, date_str: str):
        report = {
            "report_date": date_str,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            **summary,
        }
        key = f"date={date_str}/quality_report.json"
        body = json.dumps(report, ensure_ascii=False, indent=2)

        self.s3.put_object(
            Bucket="quality-reports",
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )
        logger.info({"key": key}, "Quality report saved")
        return report
