@echo off
echo ====================================================================
echo Testing LLM API Key Resolution for Document Processing
echo ====================================================================

echo.
echo 1. Testing LLM Service Health...
curl -s -w "Status: %%{http_code}\n" "http://localhost:8007/health"

echo.
echo 2. Testing Project Service Health...
curl -s -w "Status: %%{http_code}\n" "http://localhost:8002/health"

echo.
echo 3. Testing LLM Entity Extraction (this may take 20+ seconds)...
echo Please wait for response...

curl -X POST "http://localhost:8007/api/llm/process" ^
     -H "Content-Type: application/json" ^
     -H "X-Correlation-ID: test-entity-extraction" ^
     -d "{\"process_type\": \"entity_extraction\", \"prompt\": \"Extract entities from: Microsoft Azure SQL Server database\", \"project_id\": \"7d1e347c-efdd-4bc5-a112-98ec17fdf31c\"}" ^
     -w "\nHTTP Status: %%{http_code}\nTotal Time: %%{time_total}s\n" ^
     --max-time 60

echo.
echo ====================================================================
echo Test completed. Check the responses above:
echo - Health endpoints should return 200
echo - LLM process should return success:true if API keys work
echo - If you see "No API key available" errors, the configuration needs fixing
echo ====================================================================
pause