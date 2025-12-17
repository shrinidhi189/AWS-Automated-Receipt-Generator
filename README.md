# AWS-Automated-Receipt-Generator


## Overview
The AWS Automated Receipt Generator is a serverless, event-driven application that automates the processing of invoices and generation of digital receipts.

## Implementation Steps / Workflow

1. An Amazon S3 bucket was created to store incoming invoice files (images or PDF documents).

2. A DynamoDB table was set up to store extracted receipt information, using `receipt_id` as the partition key and `date` as the sort key.

3. Amazon SES (Simple Email Service) was configured by verifying an email address to enable sending receipt notification emails.

4. An IAM role was created with the required permissions, including:

   * Read access to Amazon S3
   * Access to Amazon Textract
   * Full access to DynamoDB
   * Permission to send emails using SES
   * Basic AWS Lambda execution permissions

5. An AWS Lambda function was created and associated with the IAM role.

6. The Lambda function configuration was updated by adjusting timeout settings, adding environment variables if required, and deploying the function code.

7. An event notification was configured on the S3 bucket to trigger the Lambda function whenever a new invoice file is uploaded.

8. When a file is uploaded to S3, the Lambda function:

   * Extracts invoice details using AWS Textract
   * Stores the extracted data in DynamoDB
   * Sends a receipt summary email using Amazon SES




