import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from app.config import settings

logger = logging.getLogger("email_service.mongo")


class MongoDBClient:
    def __init__(self):
        self.uri = settings.MONGODB_URI
        self.db_name = settings.MONGODB_DB_NAME
        self.client = None
        self.db = None
        self._connected = False
        
        if self.uri:
            try:
                # 3-second server selection timeout to avoid blocking startup if Mongo is down
                self.client = MongoClient(self.uri, serverSelectionTimeoutMS=3000)
                # Verify connection
                self.client.admin.command("ping")
                self.db = self.client[self.db_name]
                self._connected = True
                logger.info(f"Successfully connected to MongoDB at {self.uri} (Database: {self.db_name})")
                self._ensure_indexes()
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.warning(f"Could not connect to MongoDB: {e}. Email service will operate without DB features.")
                self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def get_collection(self, name: str):
        if not self._connected or self.db is None:
            return None
        return self.db[name]

    def _ensure_indexes(self):
        try:
            if self.db is not None:
                self.db["email_templates"].create_index("template_name", unique=True)
                self.db["suppressions"].create_index("email", unique=True)
                self.db["email_logs"].create_index("recipients")
                self.db["email_logs"].create_index([("status", 1), ("created_at", -1)])
                logger.debug("MongoDB indexes verified/created.")
        except Exception as e:
            logger.error(f"Error creating MongoDB indexes: {e}")


# Global instance
mongo_client = MongoDBClient()
