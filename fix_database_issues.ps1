# PowerShell script to fix database schema issues
# This adds missing columns and fixes foreign key constraints

Write-Host "🔄 Fixing Database Schema Issues..." -ForegroundColor Yellow

# Database connection parameters
$env:PGPASSWORD = "postgres"
$dbHost = "localhost"
$dbPort = "5432"
$dbName = "migration_platform"
$dbUser = "postgres"

# Function to execute SQL command
function Execute-SQL {
    param([string]$sql, [string]$description)
    
    Write-Host "📝 $description..." -ForegroundColor Cyan
    
    try {
        $result = psql -h $dbHost -p $dbPort -d $dbName -U $dbUser -c $sql
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ $description completed successfully" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ $description failed with exit code: $LASTEXITCODE" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "💥 Error executing $description`: $_" -ForegroundColor Red
        return $false
    }
}

# Check if psql is available
try {
    psql --version | Out-Null
    Write-Host "✅ PostgreSQL client (psql) is available" -ForegroundColor Green
} catch {
    Write-Host "❌ PostgreSQL client (psql) not found. Please install PostgreSQL client tools." -ForegroundColor Red
    exit 1
}

Write-Host "🔍 Checking database connection..." -ForegroundColor Cyan
$connectionTest = Execute-SQL "SELECT 1;" "Database connection test"
if (-not $connectionTest) {
    Write-Host "❌ Cannot connect to database. Please ensure PostgreSQL is running." -ForegroundColor Red
    exit 1
}

Write-Host "📊 Current database schema status:" -ForegroundColor Cyan

# Check if file_size column exists
Write-Host "🔍 Checking file_size column..." -ForegroundColor Cyan
$checkFileSize = @"
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'project_files' AND column_name = 'file_size'
        ) 
        THEN 'EXISTS'
        ELSE 'MISSING'
    END as file_size_status;
"@

Execute-SQL $checkFileSize "Check file_size column status"

# Add file_size column if it doesn't exist
Write-Host "📝 Adding file_size column if missing..." -ForegroundColor Cyan
$addFileSize = @"
DO `$`$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'project_files' AND column_name = 'file_size'
    ) THEN
        ALTER TABLE project_files ADD COLUMN file_size INTEGER;
        RAISE NOTICE 'Added file_size column to project_files table';
    ELSE
        RAISE NOTICE 'file_size column already exists in project_files table';
    END IF;
END `$`$;
"@

Execute-SQL $addFileSize "Add file_size column"

# Fix foreign key constraints with CASCADE DELETE
Write-Host "🔗 Fixing foreign key constraints..." -ForegroundColor Cyan

# Fix template_usage constraint (the main issue)
$fixTemplateUsage = @"
DO `$`$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'template_usage_project_id_fkey'
    ) THEN
        ALTER TABLE template_usage DROP CONSTRAINT template_usage_project_id_fkey;
    END IF;
    
    ALTER TABLE template_usage 
    ADD CONSTRAINT template_usage_project_id_fkey 
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
    
    RAISE NOTICE 'Fixed template_usage foreign key constraint';
END `$`$;
"@

Execute-SQL $fixTemplateUsage "Fix template_usage foreign key constraint"

# Fix project_files constraint
$fixProjectFiles = @"
DO `$`$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'project_files_project_id_fkey'
    ) THEN
        ALTER TABLE project_files DROP CONSTRAINT project_files_project_id_fkey;
    END IF;
    
    ALTER TABLE project_files 
    ADD CONSTRAINT project_files_project_id_fkey 
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
    
    RAISE NOTICE 'Fixed project_files foreign key constraint';
END `$`$;
"@

Execute-SQL $fixProjectFiles "Fix project_files foreign key constraint"

# Verify the changes
Write-Host "🔍 Verifying database schema fixes..." -ForegroundColor Cyan

$verifyChanges = @"
-- Check file_size column
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'project_files' AND column_name = 'file_size'
        ) 
        THEN '✅ file_size column exists'
        ELSE '❌ file_size column missing'
    END as file_size_status;

-- Check CASCADE DELETE constraints
SELECT 
    '✅ CASCADE DELETE: ' || tc.table_name || '.' || tc.constraint_name as status
FROM information_schema.table_constraints tc
JOIN information_schema.referential_constraints rc 
    ON tc.constraint_name = rc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND rc.delete_rule = 'CASCADE'
    AND tc.table_name IN ('project_files', 'template_usage')
ORDER BY tc.table_name;
"@

Execute-SQL $verifyChanges "Verify schema changes"

Write-Host "🎉 Database schema fixes completed!" -ForegroundColor Green
Write-Host "📋 Summary:" -ForegroundColor Cyan
Write-Host "   • Added file_size column to project_files table" -ForegroundColor White
Write-Host "   • Fixed foreign key constraints with CASCADE DELETE" -ForegroundColor White
Write-Host "   • Projects can now be deleted without constraint violations" -ForegroundColor White
Write-Host "   • File sizes will be properly stored and displayed" -ForegroundColor White
