import json
import os
import boto3
import uuid
from datetime import datetime
import urllib.parse

# Initialize AWS clients
s3 = boto3.client('s3')
textract = boto3.client('textract')
dynamodb = boto3.resource('dynamodb')
ses = boto3.client('ses')

# Environment variables (set these in Lambda configuration)
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'Receipts')
SES_SENDER_EMAIL = os.environ.get('SES_SENDER_EMAIL', 'YOUR_VERIFIED_EMAIL@example.com')
SES_RECIPIENT_EMAIL = os.environ.get('SES_RECIPIENT_EMAIL', 'RECIPIENT_EMAIL@example.com')

def lambda_handler(event, context):
    try:
        # Get the S3 bucket and key from the event
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'])

        print(f"Processing receipt from {bucket}/{key}")

        # Verify the object exists
        try:
            s3.head_object(Bucket=bucket, Key=key)
        except Exception as e:
            raise Exception(f"Unable to access object {key} in bucket {bucket}: {str(e)}")

        # Process receipt with Textract
        receipt_data = process_receipt_with_textract(bucket, key)

        # Store results in DynamoDB
        store_receipt_in_dynamodb(receipt_data, bucket, key)

        # Send email notification
        send_email_notification(receipt_data)

        return {
            'statusCode': 200,
            'body': json.dumps('Receipt processed successfully!')
        }
    except Exception as e:
        print(f"Error processing receipt: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }

def process_receipt_with_textract(bucket, key):
    """Process receipt using Textract's AnalyzeExpense operation"""
    response = textract.analyze_expense(
        Document={'S3Object': {'Bucket': bucket, 'Name': key}}
    )

    receipt_id = str(uuid.uuid4())
    receipt_data = {
        'receipt_id': receipt_id,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'vendor': 'Unknown',
        'total': '0.00',
        'items': [],
        's3_path': f"s3://{bucket}/{key}"
    }

    if 'ExpenseDocuments' in response and response['ExpenseDocuments']:
        expense_doc = response['ExpenseDocuments'][0]

        for field in expense_doc.get('SummaryFields', []):
            field_type = field.get('Type', {}).get('Text', '')
            value = field.get('ValueDetection', {}).get('Text', '')

            if field_type == 'TOTAL':
                receipt_data['total'] = value
            elif field_type == 'INVOICE_RECEIPT_DATE':
                receipt_data['date'] = value
            elif field_type == 'VENDOR_NAME':
                receipt_data['vendor'] = value

        for group in expense_doc.get('LineItemGroups', []):
            for line_item in group.get('LineItems', []):
                item = {}
                for field in line_item.get('LineItemExpenseFields', []):
                    ftype = field.get('Type', {}).get('Text', '')
                    val = field.get('ValueDetection', {}).get('Text', '')

                    if ftype == 'ITEM':
                        item['name'] = val
                    elif ftype == 'PRICE':
                        item['price'] = val
                    elif ftype == 'QUANTITY':
                        item['quantity'] = val

                if 'name' in item:
                    receipt_data['items'].append(item)

    return receipt_data

def store_receipt_in_dynamodb(receipt_data, bucket, key):
    table = dynamodb.Table(DYNAMODB_TABLE)
    items_for_db = [{'name': i.get('name','Unknown'), 'price': i.get('price','0.00'), 'quantity': i.get('quantity','1')} for i in receipt_data['items']]
    db_item = {
        'receipt_id': receipt_data['receipt_id'],
        'date': receipt_data['date'],
        'vendor': receipt_data['vendor'],
        'total': receipt_data['total'],
        'items': items_for_db,
        's3_path': receipt_data['s3_path'],
        'processed_timestamp': datetime.now().isoformat()
    }
    table.put_item(Item=db_item)

def send_email_notification(receipt_data):
    items_html = "".join([f"<li>{i.get('name','Unknown')} - ${i.get('price','N/A')} x {i.get('quantity','1')}</li>" for i in receipt_data['items']])
    if not items_html:
        items_html = "<li>No items detected</li>"

    html_body = f"""
    <html>
    <body>
        <h2>Receipt Processed</h2>
        <p><strong>Receipt ID:</strong> {receipt_data['receipt_id']}</p>
        <p><strong>Vendor:</strong> {receipt_data['vendor']}</p>
        <p><strong>Date:</strong> {receipt_data['date']}</p>
        <p><strong>Total Amount:</strong> ${receipt_data['total']}</p>
        <p><strong>S3 Path:</strong> {receipt_data['s3_path']}</p>
        <h3>Items:</h3>
        <ul>{items_html}</ul>
        <p>The receipt has been stored in DynamoDB.</p>
    </body>
    </html>
    """

    ses.send_email(
        Source=SES_SENDER_EMAIL,
        Destination={'ToAddresses': [SES_RECIPIENT_EMAIL]},
        Message={
            'Subject': {'Data': f"Receipt Processed: {receipt_data['vendor']} - ${receipt_data['total']}"},
            'Body': {'Html': {'Data': html_body}}
        }
    )
