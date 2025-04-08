import pymongo
import requests
import json
import logging
import time
import uuid
import argparse
from typing import List, Dict, Any, Tuple, Optional
from collections import Counter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def preprocess_candidates(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Given a document containing landscape_analysis_result with login_page_candidates,
    this function deduplicates candidates by URL. If there are duplicates and one candidate has 
    login_page_strategy 'CRAWLING', that candidate is kept.
    
    Args:
        document: The MongoDB document
        
    Returns:
        A list of dicts with keys: id, url, actions, and scan_domain
    """
    # Extract the list of candidates from the document
    candidates = document.get("landscape_analysis_result", {}).get("login_page_candidates", [])
    
    # First try to extract the scan domain from scan_config, then fall back to the top-level domain
    scan_domain = document.get("scan_config", {}).get("domain")
    if not scan_domain:
        scan_domain = document.get("domain", "")
        
    # Group candidates by their URL
    grouped = {}
    for candidate in candidates:
        url = candidate.get("login_page_candidate", "").strip()
        if not url:
            continue  # Skip if no URL is provided
        grouped.setdefault(url, []).append(candidate)
    
    # Process each group and choose one candidate per URL
    output = []
    id_counter = 1
    for url, group in grouped.items():
        # Try to find a candidate with login_page_strategy == 'CRAWLING' (case-insensitive)
        chosen = None
        for candidate in group:
            if candidate.get("login_page_strategy", "").upper() == "CRAWLING":
                chosen = candidate
                break
        # If no candidate is marked as CRAWLING, select the first candidate in the group
        if not chosen:
            chosen = group[0]
        
        # Extract the 'login_page_actions' if it exists. Otherwise, set to None
        actions = chosen.get("login_page_actions", None)
        
        # Build the output dictionary including the scan domain
        output.append({
            "id": id_counter,
            "url": url,
            "actions": actions,
            "scan_domain": scan_domain
        })
        id_counter += 1

    return output

def send_candidates_to_api(candidates: List[Dict[str, Any]], task_id: str, api_url: str) -> Tuple[bool, int, Optional[str]]:
    """
    Send the preprocessed login candidates to the API endpoint.
    
    Args:
        candidates: List of candidate dictionaries
        task_id: Task ID for correlation
        api_url: URL of the API endpoint
        
    Returns:
        A tuple: (success: bool, status_code: int, error_detail: str or None)
    """
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

    logger.info(f"Successfully sent login candidates to API for domain: {candidates[0]['scan_domain'] if candidates else 'unknown'}")
    return True, response.status_code, None


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Process MongoDB documents and count deduplicated login candidates')
    parser.add_argument('--mongo-host', default='localhost', help='MongoDB host')
    parser.add_argument('--mongo-port', type=int, default=27019, help='MongoDB port')
    parser.add_argument('--db-name', default='sso-monitor', help='MongoDB database name')
    parser.add_argument('--collection-name', default='landscape_analysis_tres', help='MongoDB collection name')
    parser.add_argument('--api-url', default='http://localhost:4050/api/login_candidates', help='API endpoint URL')
    parser.add_argument('--batch-size', type=int, default=10, help='Number of documents to process in each batch for logging')
    parser.add_argument('--delay', type=float, default=0.5, help='Delay between processing each document (seconds)')
    parser.add_argument('--limit', type=int, default=0, help='Limit the number of documents to process (0 for all)')
    parser.add_argument('--dry-run', action='store_true', help='Count URLs without sending to API')
    
    args = parser.parse_args()
    
    # MongoDB connection URI
    mongo_uri = f"mongodb://{args.mongo_host}:{args.mongo_port}/"
    
    try:
        # Connect to MongoDB
        client = pymongo.MongoClient(mongo_uri)
        db = client[args.db_name]
        collection = db[args.collection_name]
        
        logger.info(f"Connected to MongoDB: {args.db_name}.{args.collection_name} at {mongo_uri}")
        
        # Get the total number of documents (or limit if specified)
        total_docs = collection.count_documents({})
        if args.limit > 0 and args.limit < total_docs:
            total_docs = args.limit
            logger.info(f"Processing {total_docs} documents (limited by --limit)")
        else:
            logger.info(f"Found {total_docs} documents to process")
        
        # Statistics counters
        total_candidates_before_dedup = 0
        total_candidates_after_dedup = 0
        domain_counts = Counter()
        docs_with_candidates = 0
        
        # Process documents
        docs_processed = 0
        cursor = collection.find({})
        
        for document in cursor:
            if args.limit > 0 and docs_processed >= args.limit:
                break
                
            docs_processed += 1
            
            # Extract document ID for logging
            doc_id = str(document.get("_id", "unknown"))
            domain = document.get("domain", "unknown")
            
            logger.info(f"Processing document {docs_processed}/{total_docs}: {doc_id} - Domain: {domain}")
            
            # Check if the document has any login page candidates
            candidates = document.get("landscape_analysis_result", {}).get("login_page_candidates", [])
            total_candidates_before_dedup += len(candidates)
            
            if not candidates:
                logger.info(f"Document {doc_id} has no login page candidates. Skipping.")
                continue
            
            # Preprocess candidates to deduplicate and format correctly
            processed_candidates = preprocess_candidates(document)
            
            if not processed_candidates:
                logger.info(f"Document {doc_id} has no valid login page candidates after preprocessing. Skipping.")
                continue
            
            # Count the number of candidates after deduplication
            deduplicated_count = len(processed_candidates)
            total_candidates_after_dedup += deduplicated_count
            
            # Count by domain
            scan_domain = processed_candidates[0].get("scan_domain", "unknown")
            domain_counts[scan_domain] += deduplicated_count
            
            docs_with_candidates += 1
            
            logger.info(f"Document {doc_id} - Domain: {scan_domain} - Found {deduplicated_count} deduplicated login page candidates")
            
            # Generate a task ID if not present in the document
            task_id = document.get("task_config", {}).get("task_id", str(uuid.uuid4()))
            
            # Only send candidates to API if not in dry-run mode
            if not args.dry_run:
                # Send candidates to API
                success, status_code, error = send_candidates_to_api(processed_candidates, task_id, args.api_url)
                
                if not success:
                    logger.warning(f"Failed to send candidates for document {doc_id}. Will retry once.")
                    # Retry once after a short delay
                    time.sleep(2)
                    success, status_code, error = send_candidates_to_api(processed_candidates, task_id, args.api_url)
                    
                    if not success:
                        logger.error(f"Failed to send candidates for document {doc_id} after retry: {error}")
            
            # Add a small delay to avoid overwhelming the API
            time.sleep(args.delay)
            
            # Log progress periodically
            if docs_processed % args.batch_size == 0:
                logger.info(f"Progress: {docs_processed}/{total_docs} documents processed ({(docs_processed/total_docs)*100:.2f}%)")
        
        # Log final statistics
        logger.info(f"Completed processing all documents. Total: {docs_processed}")
        logger.info(f"Total documents with login page candidates: {docs_with_candidates}")
        logger.info(f"Total login page candidates before deduplication: {total_candidates_before_dedup}")
        logger.info(f"Total login page candidates after deduplication: {total_candidates_after_dedup}")
        logger.info(f"Deduplication ratio: {total_candidates_after_dedup/total_candidates_before_dedup:.2f} ({total_candidates_after_dedup}/{total_candidates_before_dedup})")
        
        logger.info("Deduplicated login page candidates by domain:")
        for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {domain}: {count} candidates")
        
    except Exception as e:
        logger.error(f"Error during processing: {e}", exc_info=True)
    finally:
        if 'client' in locals():
            client.close()
            logger.info("MongoDB connection closed")


if __name__ == "__main__":
    main()