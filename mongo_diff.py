import pymongo
import argparse
import logging
from typing import Dict, Any, List, Tuple, Set
import json
from deepdiff import DeepDiff
import pandas as pd
from tabulate import tabulate
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def connect_to_mongo(host: str, port: int, db_name: str, collection_name: str) -> pymongo.collection.Collection:
    """Connect to MongoDB and return the collection."""
    mongo_uri = f"mongodb://{host}:{port}/"
    client = pymongo.MongoClient(mongo_uri)
    db = client[db_name]
    collection = db[collection_name]
    logger.info(f"Connected to MongoDB: {db_name}.{collection_name} at {mongo_uri}")
    return collection, client

def extract_login_candidates(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract login page candidates from a document."""
    # First try to extract the domain for reference
    domain = document.get("domain", "unknown")
    
    # Extract the list of candidates from the document
    candidates = document.get("landscape_analysis_result", {}).get("login_page_candidates", [])
    
    # Process candidates to normalize them for comparison
    processed_candidates = []
    for candidate in candidates:
        url = candidate.get("login_page_candidate", "").strip()
        if not url:
            continue  # Skip if no URL is provided
            
        # Create a normalized candidate entry
        processed_candidate = {
            "url": url,
            "login_page_strategy": candidate.get("login_page_strategy", ""),
            "login_page_actions": candidate.get("login_page_actions", None),
            # Add other fields that need to be compared
        }
        processed_candidates.append(processed_candidate)
    
    # Sort candidates by URL for consistent comparison
    processed_candidates.sort(key=lambda x: x["url"])
    
    return processed_candidates

def get_document_domains(collection: pymongo.collection.Collection) -> Set[str]:
    """Get all domain values from a collection."""
    domains = collection.distinct("domain")
    return set(domains)

def get_domain_document(collection: pymongo.collection.Collection, domain: str) -> Dict[str, Any]:
    """
    Get document for a domain, ensuring each domain has at most one entry.
    If multiple documents exist for a domain, takes the most recent one.
    """
    # Find all documents for the domain
    documents = list(collection.find({"domain": domain}).sort("_id", -1).limit(1))
    
    if not documents:
        return None
    
    # Return the most recent document (assuming _id has a timestamp component)
    return documents[0]

def compare_candidates(candidates1: List[Dict], candidates2: List[Dict]) -> Tuple[Dict, List[str], List[str], int, int]:
    """
    Compare two lists of candidates and return differences.
    
    Returns:
        A tuple containing:
        - A dictionary with the DeepDiff result for shared URLs
        - A list of URLs unique to the first collection
        - A list of URLs unique to the second collection
        - Total number of candidates in first collection
        - Total number of candidates in second collection
    """
    # Extract URLs from each candidate list
    urls1 = {c["url"] for c in candidates1}
    urls2 = {c["url"] for c in candidates2}
    
    # Find URLs unique to each collection
    unique_to_1 = urls1 - urls2
    unique_to_2 = urls2 - urls1
    
    # Find common URLs
    common_urls = urls1 & urls2
    
    # For common URLs, compare the candidates in detail
    diff_results = {}
    for url in common_urls:
        # Find the candidates with this URL in each list
        cand1 = next((c for c in candidates1 if c["url"] == url), {})
        cand2 = next((c for c in candidates2 if c["url"] == url), {})
        
        # Compare the candidates
        diff = DeepDiff(cand1, cand2, ignore_order=True)
        if diff:
            diff_results[url] = diff
    
    return diff_results, list(unique_to_1), list(unique_to_2), len(urls1), len(urls2)

def format_diff_output(domain: str, diff_results: Dict, unique_to_1: List[str], unique_to_2: List[str], 
                      collection1_name: str, collection2_name: str) -> str:
    """Format the diff results into a readable output."""
    output = []
    output.append(f"\n{'='*80}")
    output.append(f"DOMAIN: {domain}")
    output.append(f"{'='*80}")
    
    # Report URLs unique to first collection
    if unique_to_1:
        output.append(f"\nLogin page candidates unique to {collection1_name}:")
        for url in unique_to_1:
            output.append(f"  + {url}")
    
    # Report URLs unique to second collection
    if unique_to_2:
        output.append(f"\nLogin page candidates unique to {collection2_name}:")
        for url in unique_to_2:
            output.append(f"  + {url}")
    
    # Report differences in common URLs
    if diff_results:
        output.append(f"\nDifferences in common login page candidates:")
        for url, diff in diff_results.items():
            output.append(f"\nURL: {url}")
            for change_type, changes in diff.items():
                if change_type in ['values_changed', 'type_changes']:
                    for path, change in changes.items():
                        output.append(f"  * {path}")
                        output.append(f"    - {collection1_name}: {change['old_value']}")
                        output.append(f"    + {collection2_name}: {change['new_value']}")
                elif change_type in ['dictionary_item_added', 'iterable_item_added']:
                    for path in changes:
                        output.append(f"  * Added in {collection2_name}: {path}")
                elif change_type in ['dictionary_item_removed', 'iterable_item_removed']:
                    for path in changes:
                        output.append(f"  * Removed in {collection2_name}: {path}")
    
    if not (unique_to_1 or unique_to_2 or diff_results):
        output.append("\nNo differences found.")
    
    return "\n".join(output)

def generate_summary(comparison_stats: Dict[str, Dict[str, int]], 
                  collection1_name: str, collection2_name: str) -> str:
    """Generate a summary of comparison results as a table."""
    # Prepare data for the table
    data = []
    for domain, stats in comparison_stats.items():
        data.append([
            domain,
            stats.get("unique_to_1", 0),
            stats.get("unique_to_2", 0),
            stats.get("different_candidates", 0),
            stats.get("total_differences", 0),
            stats.get("total_in_1", 0),
            stats.get("total_in_2", 0)
        ])
    
    # Create a pandas DataFrame for better formatting
    df = pd.DataFrame(
        data, 
        columns=["Domain", f"Unique to {collection1_name}", f"Unique to {collection2_name}", 
                "Different Candidates", "Total Differences", 
                f"Total in {collection1_name}", f"Total in {collection2_name}"]
    )
    
    # Sort by total differences descending
    df = df.sort_values(by="Total Differences", ascending=False)
    
    # Format as a table
    table = tabulate(df, headers="keys", tablefmt="grid", showindex=False)
    
    # Calculate aggregate statistics
    total_unique_to_1 = df[f"Unique to {collection1_name}"].sum()
    total_unique_to_2 = df[f"Unique to {collection2_name}"].sum()
    total_differences = df["Total Differences"].sum()
    total_in_1 = df[f"Total in {collection1_name}"].sum()
    total_in_2 = df[f"Total in {collection2_name}"].sum()
    
    # Create aggregate summary
    summary = "\n\n" + "="*80 + "\n"
    summary += "SUMMARY STATISTICS\n"
    summary += "="*80 + "\n\n"
    summary += table
    
    summary += "\n\n" + "="*80 + "\n"
    summary += "AGGREGATE METRICS\n"
    summary += "="*80 + "\n\n"
    summary += f"Total login page candidates found in {collection1_name}: {total_in_1}\n"
    summary += f"Total login page candidates found in {collection2_name}: {total_in_2}\n\n"
    
    summary += f"Unique login page candidates in {collection1_name}: {total_unique_to_1}\n"
    summary += f"Unique login page candidates in {collection2_name}: {total_unique_to_2}\n"
    summary += f"Candidates with differences: {total_differences}\n\n"
    
    # Performance comparison
    if total_in_1 > total_in_2:
        summary += f"PERFORMANCE ASSESSMENT: {collection1_name} found {total_in_1 - total_in_2} more candidates ({(total_in_1/total_in_2 - 1)*100:.1f}% more)\n"
    elif total_in_2 > total_in_1:
        summary += f"PERFORMANCE ASSESSMENT: {collection2_name} found {total_in_2 - total_in_1} more candidates ({(total_in_2/total_in_1 - 1)*100:.1f}% more)\n"
    else:
        summary += f"PERFORMANCE ASSESSMENT: Both collections found the same number of candidates.\n"
    
    return summary

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Compare login page candidates between two MongoDB collections')
    parser.add_argument('--mongo1-host', default='localhost', help='First MongoDB host')
    parser.add_argument('--mongo1-port', type=int, default=27019, help='First MongoDB port')
    parser.add_argument('--db1-name', default='sso-monitor', help='First MongoDB database name')
    parser.add_argument('--collection1-name', default='good_run_100_banks', help='First MongoDB collection name')
    
    parser.add_argument('--mongo2-host', default='localhost', help='Second MongoDB host')
    parser.add_argument('--mongo2-port', type=int, default=27019, help='Second MongoDB port')
    parser.add_argument('--db2-name', default='sso-monitor', help='Second MongoDB database name')
    parser.add_argument('--collection2-name', required=True, help='Second MongoDB collection name')
    
    parser.add_argument('--output-file', default='mongodb_diff_results.txt', help='Output file for diff results')
    parser.add_argument('--limit', type=int, default=0, help='Limit the number of domains to process (0 for all)')
    parser.add_argument('--domain-filter', help='Filter to a specific domain')
    
    # Handle issues with command-line parsing
    try:
        args = parser.parse_args()
    except Exception as e:
        logger.error(f"Error parsing arguments: {e}")
        logger.info("Tip: Make sure to use quotes around arguments with spaces or special characters.")
        logger.info("Example: python mongo_diff.py --mongo1-host localhost --collection1-name \"my collection\"")
        sys.exit(1)
    
    args = parser.parse_args()
    
    try:
        # Connect to both MongoDB collections
        collection1, client1 = connect_to_mongo(args.mongo1_host, args.mongo1_port, args.db1_name, args.collection1_name)
        collection2, client2 = connect_to_mongo(args.mongo2_host, args.mongo2_port, args.db2_name, args.collection2_name)
        
        # Get all domains from both collections
        domains1 = get_document_domains(collection1)
        domains2 = get_document_domains(collection2)
        
        logger.info(f"Found {len(domains1)} domains in {args.collection1_name}")
        logger.info(f"Found {len(domains2)} domains in {args.collection2_name}")
        
        # Find domains in both collections
        common_domains = domains1 & domains2
        logger.info(f"Found {len(common_domains)} domains common to both collections")
        
        # If domain filter is provided, filter the domains
        if args.domain_filter:
            if args.domain_filter in common_domains:
                common_domains = {args.domain_filter}
                logger.info(f"Filtering to domain: {args.domain_filter}")
            else:
                logger.error(f"Domain {args.domain_filter} not found in both collections")
                return
        
        # Apply limit if specified
        if args.limit > 0:
            common_domains = list(common_domains)[:args.limit]
            logger.info(f"Limiting to {args.limit} domains")
        
        # Open output file
        with open(args.output_file, 'w') as f:
            f.write(f"MongoDB Login Page Candidates Comparison\n")
            f.write(f"Collection 1: {args.db1_name}.{args.collection1_name}\n")
            f.write(f"Collection 2: {args.db2_name}.{args.collection2_name}\n\n")
            
            # Track statistics for summary
            comparison_stats = {}
            
            # Process each domain
            for i, domain in enumerate(sorted(common_domains)):
                logger.info(f"Processing domain {i+1}/{len(common_domains)}: {domain}")
                
                # Fetch documents from both collections (ensuring only one per domain)
                doc1 = get_domain_document(collection1, domain)
                doc2 = get_domain_document(collection2, domain)
                
                if not doc1 or not doc2:
                    logger.warning(f"Missing document for domain {domain}")
                    continue
                
                # Extract login candidates
                candidates1 = extract_login_candidates(doc1)
                candidates2 = extract_login_candidates(doc2)
                
                # Compare candidates
                diff_results, unique_to_1, unique_to_2, total_in_1, total_in_2 = compare_candidates(candidates1, candidates2)
                
                # Format and write the diff output
                diff_output = format_diff_output(
                    domain, diff_results, unique_to_1, unique_to_2, 
                    args.collection1_name, args.collection2_name
                )
                f.write(diff_output)
                
                # Track statistics
                comparison_stats[domain] = {
                    "unique_to_1": len(unique_to_1),
                    "unique_to_2": len(unique_to_2),
                    "different_candidates": len(diff_results),
                    "total_differences": len(unique_to_1) + len(unique_to_2) + len(diff_results),
                    "total_in_1": total_in_1,
                    "total_in_2": total_in_2
                }
            
            # Generate and write summary
            summary = generate_summary(comparison_stats, args.collection1_name, args.collection2_name)
            f.write(summary)
            
        logger.info(f"Comparison complete. Results written to {args.output_file}")
        
    except Exception as e:
        logger.error(f"Error during processing: {e}", exc_info=True)
    finally:
        # Close MongoDB connections
        if 'client1' in locals():
            client1.close()
        if 'client2' in locals():
            client2.close()
        logger.info("MongoDB connections closed")


if __name__ == "__main__":
    main()