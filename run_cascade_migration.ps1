# PowerShell script to run the cascade delete migration
# This fixes the foreign key constraint violation when deleting projects

Write-Host "🔄 Running Foreign Key Cascade Delete Migration..." -ForegroundColor Yellow

# Set environment variables
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/migration_platform"

# Change to project-service directory
Push-Location "project-service"

try {
    Write-Host "📝 Running migration script..." -ForegroundColor Cyan
    python migrate_cascade_deletes.py
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Migration completed successfully!" -ForegroundColor Green
        Write-Host "📋 Projects can now be deleted without foreign key constraint violations" -ForegroundColor Green
    } else {
        Write-Host "❌ Migration failed with exit code: $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
} catch {
    Write-Host "💥 Error running migration: $_" -ForegroundColor Red
    exit 1
} finally {
    Pop-Location
}

Write-Host "🎉 Migration process completed!" -ForegroundColor Green
