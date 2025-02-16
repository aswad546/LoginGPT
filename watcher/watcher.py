from pymongo import MongoClient
import os
import logging


logger = logging.getLogger(__name__)

MONGO_HOST = os.getenv("MONGO_HOST", "mongodb")  # Use the Docker service name
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
DATABASE_NAME = os.getenv("DATABASE_NAME", "sso-monitor")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "landscape_analysis_tres")

def watch_collection():
    """Watches for new inserts in MongoDB collection."""
    logger.info(f"Lookie here: mongodb://{MONGO_HOST}:{MONGO_PORT}/")
    print(f"Lookie here: mongodb://{MONGO_HOST}:{MONGO_PORT}/")
    client = MongoClient(f"mongodb://{MONGO_HOST}:{MONGO_PORT}/")
    db = client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]

    with collection.watch([{"$match": {"operationType": "insert"}}]) as stream:
        print(f"Watching for new entries in {DATABASE_NAME}.{COLLECTION_NAME}...")
        logger.info(f"Watching for new entries in {DATABASE_NAME}.{COLLECTION_NAME}...")
        for change in stream:
            print(f"New entry detected: {change['fullDocument']}")
            logger.info(f"New entry detected: {change['fullDocument']}")

if __name__ == "__main__":
    watch_collection()
