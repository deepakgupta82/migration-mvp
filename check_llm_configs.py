import os
os.environ['DATABASE_URL'] = 'postgresql://projectuser:projectpass@localhost:5432/projectdb'
from database import get_db, LLMConfigurationModel

db = next(get_db())
configs = db.query(LLMConfigurationModel).all()
print(f'Found {len(configs)} LLM configurations:')
for config in configs:
    print(f'ID: {config.id}, Name: {config.name}, Provider: {config.provider}, API Key Length: {len(config.api_key) if config.api_key else 0}, API Key Value: {repr(config.api_key)}')
db.close()
