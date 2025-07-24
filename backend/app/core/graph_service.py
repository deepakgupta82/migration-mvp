from neo4j import GraphDatabase
import logging
import os

# Database logging setup
os.makedirs("logs", exist_ok=True)
db_logger = logging.getLogger("database")
db_handler = logging.FileHandler("logs/database.log")
db_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
if not db_logger.hasHandlers():
    db_logger.addHandler(db_handler)
db_logger.setLevel(logging.INFO)

class GraphService:
    def __init__(self):
        # Support both Docker Compose and Kubernetes service names
        neo4j_url = os.getenv("NEO4J_URL", "bolt://neo4j-service:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_password))

    def close(self):
        self.driver.close()

    def execute_query(self, query, parameters=None):
        with self.driver.session() as session:
            results = session.run(query, parameters)
            return [record for record in results]
