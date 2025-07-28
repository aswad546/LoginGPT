#!/usr/bin/env python3
import pymongo
import json
import requests
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def preprocess_candidates(input_json):
    """
    Given an input JSON object containing landscape_analysis_result with login_page_candidates,
    this function deduplicates candidates by URL. If there are duplicates and one candidate has 
    login_page_strategy 'CRAWLING', that candidate is kept.
    
    The output is a list of dicts with keys: id, url, actions, and scan_domain.
    """
    # Extract the list of candidates from the input JSON.
    candidates = input_json.get("landscape_analysis_result", {}).get("login_page_candidates", [])
    
    # First try to extract the scan domain from scan_config, then fall back to the top-level domain.
    scan_domain = input_json.get("scan_config", {}).get("domain")
    if not scan_domain:
        scan_domain = input_json.get("domain", "")
        
    # Group candidates by their URL.
    grouped = {}
    for candidate in candidates:
        url = candidate.get("login_page_candidate", "").strip()
        if not url:
            continue  # Skip if no URL is provided.
        grouped.setdefault(url, []).append(candidate)
    
    # Process each group and choose one candidate per URL.
    output = []
    id_counter = 1
    for url, group in grouped.items():
        # Try to find a candidate with login_page_strategy == 'CRAWLING' (case-insensitive)
        chosen = None
        for candidate in group:
            if candidate.get("login_page_strategy", "").upper() == "CRAWLING":
                chosen = candidate
                break
        # If no candidate is marked as CRAWLING, select the first candidate in the group.
        if not chosen:
            chosen = group[0]
        
        # Extract the 'login_page_actions' if it exists. Otherwise, set to None.
        actions = chosen.get("login_page_actions", None)
        
        # Build the output dictionary including the scan domain.
        output.append({
            "id": id_counter,
            "url": url,
            "actions": actions,  # This will be None if not present.
            "scan_domain": scan_domain
        })
        id_counter += 1

    return output

def send_candidates_to_api(candidates, task_id):
    """
    Send the preprocessed login candidates to a remote API endpoint.
    'candidates' should be a Python list/dict that can be serialized to JSON.
    
    Returns a tuple: (success: bool, status_code: int, error_detail: str or None)
    """
    api_url = "http://localhost:4050/api/login_candidates"
    payload = json.dumps({
        "candidates": candidates, 
        "task_id": task_id
    })
    
    try:
        response = requests.post(
            api_url,
            data=payload,
            headers={'Content-Type': 'application/json'},
        )
        if response.status_code != 200:
            error_detail = (f"API responded with status code {response.status_code}. "
                            f"Response: {response.text}")
            logger.warning("Failed to send candidates to API. %s", error_detail)
            return False, response.status_code, error_detail
    except requests.exceptions.ConnectionError as e:
        error_detail = f"Connection error: {str(e)}"
        logger.error("Connection error: API is down or unreachable. Error: %s", error_detail, exc_info=True)
        return False, 0, error_detail
    except requests.exceptions.Timeout as e:
        error_detail = f"Timeout error: {str(e)}"
        logger.error("Request timed out. API might be slow or down. Error: %s", error_detail, exc_info=True)
        return False, 0, error_detail
    except Exception as e:
        error_detail = f"Unexpected error: {str(e)}"
        logger.error("Unexpected error when sending candidates to API: %s", error_detail, exc_info=True)
        return False, 0, error_detail

    logger.info("Successfully sent login candidates to API at %s", api_url)
    return True, response.status_code, None

def update_document(collection, doc_id, api_status, api_error):
    """Update the MongoDB document with the API response status and error."""
    collection.update_one(
        {"_id": doc_id},
        {"$set": {"api_status": api_status, "api_error": api_error}}
    )
    logger.info(f"Updated document {doc_id} with api_status={api_status}")

def process_batch(collection, batch, success_count, failure_count):
    """Process a batch of documents."""
    for doc in batch:
        task_id = doc.get("task_config", {}).get("task_id")
        if not task_id:
            logger.warning(f"No task_id found for document {doc['_id']}, skipping")
            continue
            
        # Preprocess candidates
        candidates = preprocess_candidates(doc)
        logger.info(f"Preprocessed {len(candidates)} candidates for task_id: {task_id}")
        
        # Skip if no candidates found
        if not candidates:
            logger.warning(f"No candidates found for document {doc['_id']}, skipping")
            continue
            
        # Send candidates to API
        success, status_code, error_detail = send_candidates_to_api(candidates, task_id)
        
        # Update document with result
        update_document(collection, doc["_id"], status_code, error_detail)
        
        if success:
            success_count += 1
        else:
            failure_count += 1
            
        # Add a small delay to avoid overloading the API
        time.sleep(1)
    
    return success_count, failure_count

def main():
    # MongoDB connection details
    mongo_host = "localhost"
    mongo_port = 27019
    db_name = "sso-monitor"
    collection_name = "landscape_analysis_tres"
    
    # Connect to MongoDB
    try:
        # Set a high socketTimeoutMS to prevent timeouts during long-running operations
        client = pymongo.MongoClient(
            mongo_host, 
            mongo_port,
            socketTimeoutMS=300000,  # 5 minutes
            connectTimeoutMS=60000,  # 1 minute
            serverSelectionTimeoutMS=60000  # 1 minute
        )
        db = client[db_name]
        collection = db[collection_name]
        logger.info(f"Connected to MongoDB at {mongo_host}:{mongo_port}")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return
    
    # Find total count of documents with api_status = 0
    total_count = collection.count_documents({"api_status": 0})
    logger.info(f"Found {total_count} documents with api_status=0")
    
    # Process documents in batches to avoid cursor timeout
    batch_size = 100
    success_count = 0
    failure_count = 0
    
    # Save the last processed ID to resume from there if needed
    last_id = None
    processed_count = 0
    
    while processed_count < total_count:
        # Construct query - if we have a last_id, start from there
        query = {"api_status": 0}
        if last_id:
            query["_id"] = {"$gt": last_id}
        
        # Get a batch of documents, sort by _id to ensure consistent ordering
        batch = list(collection.find(query).sort("_id", 1).limit(batch_size))
        
        if not batch:
            logger.info("No more documents to process")
            break
        
        # Save the last ID from this batch
        last_id = batch[-1]["_id"]
        
        try:
            # Process this batch
            success_count, failure_count = process_batch(
                collection, batch, success_count, failure_count
            )
            processed_count += len(batch)
            logger.info(f"Processed {processed_count}/{total_count} documents")
            
        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            logger.error(f"Last processed ID: {last_id}")
            # Wait a bit before retrying
            time.sleep(10)
    
    logger.info(f"Completed processing. Success: {success_count}, Failures: {failure_count}")

if __name__ == "__main__":
    main()