"""
Searchable Docs resource with fragments support for large documents.

This module implements TWO tables:
1. 'searchable_docs' - Main table (schema determined by your fetch_data function)
2. 'searchable_docs_fragments' - Fragments table (schema determined by your fetch_fragments_data function)

IMPORTANT: You define both table schemas through your returned data structure.
Zeeker does not enforce any specific field names or relationships.

The database is built using sqlite-utils with automatic schema detection.
"""
from sqlite_utils.db import Table, NotFoundError
from typing import Optional, List, Dict, Any


def fetch_data(existing_table: Optional[Table]) -> List[Dict[str, Any]]:
    """
    Fetch data for the searchable_docs table.

    Args:
        existing_table: sqlite-utils Table object if table exists, None for new table
                       Use this to check for existing data and avoid duplicates

    Returns:
        List[Dict[str, Any]]: Records for the main table

    IMPORTANT - Schema Considerations:
    Your FIRST fetch_data() call determines the column types permanently!
    sqlite-utils infers types from the first ~100 records and locks them in.

    You have complete freedom to define your schema. Common patterns:
    - Simple: {"id": 1, "title": "Doc 1", "content": "..."}
    - Metadata focused: {"id": 1, "title": "Doc 1", "source": "...", "date": "..."}
    - Complex: {"id": 1, "title": "Doc 1", "metadata": {"tags": ["tag1"]}, "status": "active"}
    
    CRITICAL - Duplicate Handling:
    Your function MUST NOT return records with IDs that already exist in the database.
    sqlite-utils will throw a UNIQUE constraint error if you do!
    
    Example usage:
        if existing_table:
            # REQUIRED: Get existing IDs to avoid duplicates
            existing_ids = {row["id"] for row in existing_table.rows}
            print(f"Found {len(existing_ids)} existing records")
            
            # Fetch fresh data and filter duplicates
            fresh_data = get_documents_from_source()
            new_records = [
                record for record in fresh_data 
                if record["id"] not in existing_ids
            ]
            print(f"Adding {len(new_records)} new records")
            
            # Optional: Access metadata for incremental updates
            db = existing_table.db
            if "_zeeker_updates" in db.table_names():
                updates_table = db["_zeeker_updates"]
                try:
                    metadata = updates_table.get(existing_table.name)
                    last_updated = metadata["last_updated"]  # ISO datetime string
                    record_count = metadata["record_count"]  # Current row count
                    print(f"Last updated: {last_updated}, Records: {record_count}")
                except NotFoundError:
                    print("No metadata found - first run")
            
            return new_records
        else:
            print("Creating new table")
            return get_documents_from_source()
    """
    # TODO: Implement your data fetching logic
    # This is just an example - replace with your actual schema and data
    return [
        {
            "id": 1,  # Required: some kind of identifier
            "title": "Example Document",  # Your field names and types
            "content": "Document content...",  # You decide what goes in main vs fragments
            # Add any other fields your project needs
        },
        # Add more records...
    ]


def fetch_fragments_data(existing_fragments_table: Optional[Table], main_data_context: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    Fetch fragments data for the searchable_docs_fragments table.

    This is called automatically after fetch_data().

    Args:
        existing_fragments_table: sqlite-utils Table object if exists, None for new table
                                 Use this to check existing fragments and avoid duplicates
        main_data_context: Raw data from fetch_data() to avoid duplicate API calls (optional)
                          Contains the same data returned by your fetch_data() function

    Returns:
        List[Dict[str, Any]]: Fragment records with YOUR chosen schema

    IMPORTANT: You have complete freedom to define the fragments schema.
    Common patterns include:

    1. Simple text chunks:
       {"parent_id": 1, "text": "fragment content"}

    2. Positional fragments:
       {"doc_id": 1, "position": 0, "content": "...", "length": 500}

    3. Semantic fragments:
       {"document_id": 1, "section_type": "intro", "text": "...", "page": 1}

    4. Custom fragments:
       {"source_id": 1, "fragment_data": "...", "metadata": {"type": "citation"}}

    The only requirement: some way to link fragments back to main records.
    """
    # TODO: Implement your fragments logic
    # This is just an example - replace with your actual implementation

    # OPTION 1: Use main_data_context to avoid duplicate API calls
    if main_data_context:
        fragments = []
        for main_record in main_data_context:
            # Use data already fetched in fetch_data() - no duplicate API calls!
            doc_content = main_record.get("content", "")  # Or however you store content
            doc_id = main_record.get("id")  # Or your identifier field

            # Split the content into fragments
            chunks = doc_content.split("\n\n")  # Or your preferred splitting logic
            for i, chunk in enumerate(chunks):
                if chunk.strip():
                    fragments.append(
                        {
                            "parent_id": doc_id,  # Link to main table record
                            "fragment_num": i,  # Fragment ordering
                            "text": chunk.strip(),  # Fragment content
                            "char_count": len(chunk),  # Your metadata
                        }
                    )
        return fragments

    # OPTION 2: Fallback to independent data fetch (for backward compatibility)
    # This runs when main_data_context is None (e.g., testing, old resources)
    example_text = """
    This is an example document that will be split into fragments.
    You can implement any splitting logic you need.

    Maybe you want sentence-based fragments, paragraph-based,
    or even semantic chunks based on document structure.

    The choice is entirely yours based on your project needs.
    """

    # Your splitting logic goes here
    fragments = []
    sentences = example_text.split(".")
    for i, sentence in enumerate(sentences):
        if sentence.strip():
            fragments.append(
                {
                    "parent_id": 1,  # Link to main table (your choice of field name)
                    "sequence": i,  # Your choice of ordering
                    "text": sentence.strip(),  # Your choice of content field name
                    # Add any other fields your fragments need
                }
            )

    return fragments


def transform_data(raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Optional: Transform main table data before database insertion.

    Args:
        raw_data: The data returned from fetch_data()

    Returns:
        List[Dict[str, Any]]: Transformed data
    """
    # TODO: Add any data transformation logic here
    return raw_data


def transform_fragments_data(raw_fragments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Optional: Transform fragment data before database insertion.

    Args:
        raw_fragments: The data returned from fetch_fragments_data()

    Returns:
        List[Dict[str, Any]]: Transformed fragment data
    """
    # TODO: Add any fragment processing logic here
    return raw_fragments


# TODO: Add any helper functions your project needs
# Examples:
# - Document parsing functions
# - Text splitting utilities
# - Data validation functions
# - API client functions