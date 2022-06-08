from PyPDF2 import PdfFileWriter, PdfFileReader

import json
import boto3
import uuid
import datetime

s3_client = boto3.client("s3")
dynamodb_client = boto3.client("dynamodb", region_name="us-west-2")


class Params:
    def __init__(self, event):
        self.event = event

    @property
    def upload_object(self) -> dict:
        key = self.event["Records"][0]["s3"]["object"]["key"]
        return {"key": key, "file_name": key.split('/')[-1]}

    @property
    def buckets(self) -> dict:
        return {
            "source": self.event["Records"][0]["s3"]["bucket"]["name"],
            "destination": "drivingchange-processed-documents"
        }


def process_pdf(file_name, file_id):
    pass


def dispatch(event):
    params = Params(event)
    file_path = f"/tmp/{params.upload_object['file_name']}"
    document_id = str(uuid.uuid4())

    # get file from s3 bucket
    with open(file_path, "wb") as file:
        s3_client.download_fileobj(params.buckets["source"], params.upload_object["key"], file)

    file_extension = (params.upload_object["file_name"]).split(".")[-1].lower()
    if file_extension == "pdf":
        process_pdf(file_path, document_id)


def lambda_handler(event, context):
    key = event["Records"][0]["s3"]["object"]["key"]
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    processed_bucket = "drivingchange-processed-documents"

    # get file from s3 bucket
    file_path = f'/tmp/{key.split("/")[-1]}'
    with open(file_path, "wb") as file:
        s3_client.download_fileobj(bucket, key, file)

    # split file into multiple pages
    pdf_file = PdfFileReader(open(file_path, "rb"))
    for i in range(pdf_file.numPages):
        data = PdfFileWriter()
        data.add_page(pdf_file.getPage(i))
        with open(f'{file_path}-{i}', "wb") as output_file:
            data.write(output_file)

    # add file into processed s3 bucket
    pdf_id = str(uuid.uuid4())
    for i in range(pdf_file.numPages):
        with open(f'{file_path}-{i}', "rb") as file:
            s3_client.put_object(
                Body=file,
                Key=f'{pdf_id}/images/{key.split("/")[-1]}-{i}',
                Bucket=processed_bucket,
            )

    # add file to dynamodb
    dynamodb_client.put_item(
        TableName="documents-dev-poc",
        Item={
            "document_id": {
                "S": pdf_id
            },
            "create_date": {
                "S": datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            },
            "Filename": {
                "S": key.split("/")[-1]
            },
            "PageCount": {
                "N": str(pdf_file.numPages)
            }
        }
    )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "hello world, nothing is something or is it?",
        })
    }
