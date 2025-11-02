from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import boto3
from fastapi.middleware.cors import CORSMiddleware
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import os
from typing import Optional

# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="S3 File Upload Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for now, allow all origins (you can restrict later)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# S3 Configuration from .env
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")  # Default region if not specified
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "study2material")

# Validate that required credentials are present
if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    raise ValueError("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set in .env file")

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "S3 File Upload API",
        "bucket": S3_BUCKET_NAME,
        "endpoints": {
            "upload": "/upload",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test S3 connection by listing bucket
        s3_client.head_bucket(Bucket=S3_BUCKET_NAME)
        return {
            "status": "healthy",
            "bucket": S3_BUCKET_NAME,
            "connection": "success"
        }
    except ClientError as e:
        return {
            "status": "unhealthy",
            "bucket": S3_BUCKET_NAME,
            "error": str(e)
        }


@app.post("/upload")
async def upload_file(file: UploadFile = File(...), folder: Optional[str] = None):
    """
    Upload a file to S3 bucket
    
    Args:
        file: The file to upload
        folder: Optional folder/path within the bucket (e.g., "documents/", "images/")
    
    Returns:
        JSON response with upload status and file URL
    """
    try:
        # Read file contents
        file_contents = await file.read()
        
        # Construct S3 key (path in bucket)
        if folder:
            # Ensure folder ends with /
            folder = folder.rstrip('/') + '/'
            s3_key = f"{folder}{file.filename}"
        else:
            s3_key = file.filename
        
        # Upload to S3
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_contents,
            ContentType=file.content_type,
            ACL='public-read' 
        )
        
        # Generate URL for the uploaded file
        file_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "File uploaded successfully",
                "filename": file.filename,
                "s3_key": s3_key,
                "bucket": S3_BUCKET_NAME,
                "url": file_url,
                "content_type": file.content_type,
                "size": len(file_contents)
                
            }
        )
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        raise HTTPException(
            status_code=500,
            detail=f"S3 upload failed: {error_code} - {error_message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


@app.post("/upload-multiple")
async def upload_multiple_files(files: list[UploadFile] = File(...), folder: Optional[str] = None):
    """
    Upload multiple files to S3 bucket
    
    Args:
        files: List of files to upload
        folder: Optional folder/path within the bucket
    
    Returns:
        JSON response with upload status for all files
    """
    results = []
    errors = []
    
    for file in files:
        try:
            # Read file contents
            file_contents = await file.read()
            
            # Construct S3 key
            if folder:
                folder = folder.rstrip('/') + '/'
                s3_key = f"{folder}{file.filename}"
            else:
                s3_key = file.filename
            
            # Upload to S3
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=s3_key,
                Body=file_contents,
                ContentType=file.content_type
            )
            
            file_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
            
            results.append({
                "filename": file.filename,
                "status": "success",
                "s3_key": s3_key,
                "url": file_url
            })
            
        except Exception as e:
            errors.append({
                "filename": file.filename,
                "status": "failed",
                "error": str(e)
            })
    
    return JSONResponse(
        status_code=200,
        content={
            "message": f"Processed {len(files)} file(s)",
            "successful": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)




