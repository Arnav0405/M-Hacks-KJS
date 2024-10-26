# test_mongodb.py
from pymongo import MongoClient
from mongodb_config import MONGODB_CONFIG

def test_mongodb_connection():
    try:
        # Create a MongoDB client
        client = MongoClient(
            host=MONGODB_CONFIG['host'],
            port=MONGODB_CONFIG['port']
        )
        
        # Test the connection
        client.server_info()
        print("MongoDB connection successful!")
        
        # Test database and collection creation
        db = client[MONGODB_CONFIG['db_name']]
        collection = db[MONGODB_CONFIG['collection_name']]
        
        # Insert a test document
        test_doc = {"test": "document"}
        result = collection.insert_one(test_doc)
        print(f"Test document inserted with id: {result.inserted_id}")
        
        # Retrieve the test document
        retrieved_doc = collection.find_one({"test": "document"})
        print(f"Retrieved test document: {retrieved_doc}")
        
        # Clean up - delete test document
        collection.delete_one({"test": "document"})
        print("Test document cleaned up")
        
        return True
    except Exception as e:
        print(f"MongoDB test failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_mongodb_connection()