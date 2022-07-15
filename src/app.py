import os

from pdf2image import convert_from_bytes

import boto3
import re
import uuid
import datetime
from urllib.parse import unquote


s3_client = boto3.client("s3")
dynamodb_client = boto3.client("dynamodb")
upload_bucket = "drivingchange-sample-documents"
processed_bucket = "drivingchange-processed-documents"


def process_pdf(document, file_name):
    """Convert PDF to images"""
    pages = convert_from_bytes(document, poppler_path="/var/task/poppler/bin/")
    for index, page in enumerate(pages):
        page.save(f"{file_name}-{index + 1}.png", "PNG")


def lambda_handler(event, context):
    key = event["Records"][0]["s3"]["object"]["key"]
    key = unquote(key.replace("+", " "))  # url decode
    document_id = str(uuid.uuid4())
    print(f'Proccessing Started:', key)

    # get file from uploaded s3 bucket
    document = s3_client.get_object(Key=key, Bucket=upload_bucket)["Body"].read()
    print(f'Downloaded PDF from S3 upload bucket')

    # convert to png images
    file_name = f"/tmp/{re.match(r'^(?:.*/)?(.*).(?:pdf|PDF)$', key).group(1)}"
    process_pdf(document, file_name)
    print("PDF has been converted to images")

    # upload images to secondary s3
    images = [i for i in os.listdir("/tmp/") if i.endswith(".png")]
    for image in images:
        with open(f'/tmp/{image}', "rb") as image_file:
            s3_client.upload_fileobj(image_file, processed_bucket, f'{document_id}/images/{image}')
    print("Images has been uploaded to the secondary S3 bucket")

    # add docoument to dynamodb
    dynamodb_client.put_item(
        TableName="documents-dev-poc",
        Item={
            "document_id": {
                "S": document_id
            },
            "create_date": {
                "S": datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            },
            "Filename": {
                "S": key
            },
            "PageCount": {
                "N": str(len(images))
            }
        }
    )
    print("Added to dynamodb:", document_id)

    return {"statusCode": 200}
