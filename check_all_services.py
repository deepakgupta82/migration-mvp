import requests
import time

services = [
    {"name": "🌐 Frontend", "url": "http://localhost:3000"},
    {"name": "🧠 Backend API", "url": "http://localhost:8000/health"},
    {"name": "📊 Project Service", "url": "http://localhost:8002/health"},
    {"name": "📄 Reporting Service", "url": "http://localhost:8001/health"},
    {"name": "🗄️ Neo4j Browser", "url": "http://localhost:7474"},
    {"name": "🔍 Weaviate", "url": "http://localhost:8080/v1/meta"},
    {"name": "📁 MinIO Console", "url": "http://localhost:9001"},
]

print("🚀 Checking all platform services...")
print("=" * 60)

all_healthy = True

for service in services:
    try:
        response = requests.get(service["url"], timeout=5)
        if response.status_code == 200:
            print(f"✅ {service['name']}: HEALTHY")
        else:
            print(f"❌ {service['name']}: UNHEALTHY (HTTP {response.status_code})")
            all_healthy = False
    except Exception as e:
        print(f"❌ {service['name']}: UNREACHABLE ({str(e)})")
        all_healthy = False

print("=" * 60)
if all_healthy:
    print("🎉 ALL SERVICES ARE RUNNING SUCCESSFULLY!")
else:
    print("⚠️  SOME SERVICES ARE DOWN - CHECK ABOVE")
