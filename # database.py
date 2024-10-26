# database.py
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database
import logging
from typing import Tuple
import datetime


logger = logging.getLogger(__name__)

class MongoDB:
    def __init__(self, connection_string: str, db_name: str):
        self.client = MongoClient(connection_string)
        self.db = self.client[db_name]
        self.emails = self.db.emails
        self.analysis_results = self.db.analysis_results
        self._setup_indexes()

    def _setup_indexes(self):
        # Create indexes for better query performance
        self.emails.create_index([("date", DESCENDING)])
        self.emails.create_index([("sender", ASCENDING)])
        self.emails.create_index([("subject", ASCENDING)])
        self.analysis_results.create_index([("email_id", ASCENDING)])
        self.analysis_results.create_index([("analysis_timestamp", DESCENDING)])

    def insert_email(self, email_data: dict) -> str:
        result = self.emails.insert_one(email_data)
        return str(result.inserted_id)

    def insert_analysis(self, analysis_data: dict) -> str:
        result = self.analysis_results.insert_one(analysis_data)
        return str(result.inserted_id)

    def get_email_by_id(self, email_id: str) -> dict:
        return self.emails.find_one({"_id": email_id})

    def get_analysis_by_email_id(self, email_id: str) -> dict:
        return self.analysis_results.find_one({"email_id": email_id})

    def get_emails_by_date_range(self, start_date: datetime, end_date: datetime):
        return self.emails.find({
            "date": {
                "$gte": start_date,
                "$lte": end_date
            }
        }).sort("date", DESCENDING)

    def get_emails_by_sentiment(self, min_score: float, max_score: float):
        return self.analysis_results.find({
            "sentiment_score": {
                "$gte": min_score,
                "$lte": max_score
            }
        })

    def update_email_analysis(self, email_id: str, analysis_data: dict):
        return self.analysis_results.update_one(
            {"email_id": email_id},
            {"$set": analysis_data},
            upsert=True
        )