# Fix file download and document processing issues

## Issues Fixed

### 1. React Error Fixes (FileUpload component and gateway router)
- **Problem**: Objects with keys `{filename, size, last_modified, content_type, key}` were being rendered directly as React children
- **Root Cause**: Gateway router was returning detailed file objects instead of expected format, and error objects were being rendered directly
- **Solution**: 
  - Fixed gateway router `/api/projects/{project_id}/uploaded-files` endpoint to transform storage service response to expected frontend format
  - Improved error handling in FileUpload component to convert error objects to strings before rendering

### 2. File Download Functionality
- **Problem**: File download endpoint returning 404 errors for uploaded files
- **Root Cause**: Download endpoint was using backend storage service directly instead of routing to storage service microservice
- **Solution**: 
  - Refactored `/api/projects/{project_id}/download/{filename}` endpoint to properly route to storage service
  - Added proper URL encoding for filenames with spaces and special characters
  - Implemented fallback logic to check both `uploads_raw` and `uploads_parsed` storage categories

### 3. Document Processing Endpoint
- **Problem**: Document processing endpoint returning 404 errors
- **Root Cause**: Endpoint was expecting multipart form data but frontend was sending JSON with selected files
- **Solution**: 
  - Fixed `/api/projects/{project_id}/process-documents` endpoint to handle JSON requests from frontend
  - Added proper routing to document service with correct request format
  - Implemented logic to handle both selected files and process-all scenarios

### 4. Document Service Dependencies
- **Problem**: MarkItDown PDF conversion failing with missing dependency errors
- **Root Cause**: Document service requirements.txt missing PDF processing dependencies and httpx
- **Solution**: 
  - Updated `services/document-service/requirements.txt` to include `markitdown[pdf,docx,pptx,xlsx,xls]>=0.1.2`
  - Added missing `httpx` and `python-dotenv` dependencies

## Files Modified

### Backend Gateway Router
- `backend/app/routers/gateway_router.py`
  - Fixed file download endpoint to route to storage service
  - Fixed document processing endpoint to handle JSON requests and route to document service
  - Fixed uploaded files listing endpoint to return expected format

### Document Service
- `services/document-service/requirements.txt`
  - Added MarkItDown with PDF support
  - Added missing httpx dependency

### Frontend Error Handling
- `frontend/src/components/FileUpload.tsx`
  - Improved error message handling to prevent object rendering

## Testing
- Created comprehensive test scripts to verify functionality
- Verified storage service is running and connected to MinIO
- Confirmed file uploads are working correctly
- File download and document processing endpoints now properly route to microservices

## Architecture Compliance
- Maintains microservices architecture with proper service-to-service communication
- Gateway router now correctly proxies requests to appropriate services
- No direct backend imports or cross-service dependencies
- Proper error handling and logging throughout

## Expected Results
- File downloads work for files with spaces and special characters
- Document processing accepts selected files and initiates processing via document service
- React rendering errors resolved
- MarkItDown PDF conversion works with proper dependencies
