"""
Template generation for Zeeker resources.

This module handles generating Python resource files from Jinja2 templates.
Extracted from project.py to follow separation of concerns.
"""

from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader

    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False



class ResourceTemplateGenerator:
    """Generates Python resource files from Jinja2 templates."""

    def __init__(self):
        """Initialize the template generator."""
        self.templates_dir = Path(__file__).parent.parent / "templates"
        if HAS_JINJA2 and self.templates_dir.exists():
            self.env = Environment(
                loader=FileSystemLoader(str(self.templates_dir)),
                trim_blocks=True,
                lstrip_blocks=True,
            )
        else:
            self.env = None

    def generate_resource_template(self, resource_name: str, fragments: bool = False) -> str:
        """Generate a Python template for a resource.

        Args:
            resource_name: Name of the resource
            fragments: Whether to generate fragments-enabled template

        Returns:
            Generated Python code as string
        """
        if self.env and HAS_JINJA2:
            return self._generate_jinja2_template(resource_name, fragments)
        else:
            # Fallback to string-based templates if Jinja2 not available
            return self._generate_fallback_template(resource_name, fragments)

    def _generate_jinja2_template(self, resource_name: str, fragments: bool) -> str:
        """Generate template using Jinja2."""
        template_file = "fragments.py.j2" if fragments else "resource.py.j2"

        try:
            template = self.env.get_template(template_file)
            return template.render(resource_name=resource_name)
        except Exception:
            # Fall back to string-based templates if Jinja2 fails
            return self._generate_fallback_template(resource_name, fragments)

    def _generate_fallback_template(self, resource_name: str, fragments: bool) -> str:
        """Generate template using string formatting (fallback)."""
        if fragments:
            return self._generate_fragments_fallback(resource_name)
        else:
            return self._generate_standard_fallback(resource_name)

    def _generate_standard_fallback(self, resource_name: str) -> str:
        """Generate standard resource template using string formatting."""
        return f'''"""
{resource_name.replace('_', ' ').title()} resource for fetching and processing data.

This module should implement a fetch_data() function that returns
a list of dictionaries to be inserted into the '{resource_name}' table.

The database is built using sqlite-utils, which provides:
• Automatic table creation from your data structure
• Type inference (integers → INTEGER, floats → REAL, strings → TEXT)
• JSON support for complex data (lists, dicts stored as JSON)
• Safe data insertion without SQL injection risks
"""

def fetch_data(existing_table):
    """
    Fetch data for the {resource_name} table.

    Args:
        existing_table: sqlite-utils Table object if table exists, None for new table
                       Use this to check for existing data and avoid duplicates

    Returns:
        List[Dict[str, Any]]: List of records to insert into database

    IMPORTANT - Schema Considerations:
    Your FIRST fetch_data() call determines the column types permanently!
    sqlite-utils infers types from the first ~100 records and locks them in.
    Later runs cannot change existing column types, only add new columns.

    Python Type → SQLite Column Type:
    • int          → INTEGER
    • float        → REAL
    • str          → TEXT
    • bool         → INTEGER (stored as 0/1)
    • dict/list    → TEXT (stored as JSON)
    • None values  → Can cause type inference issues

    Best Practices:
    1. Make sure your first batch has correct Python types
    2. Use consistent data types across all records
    3. Avoid None/null values in key columns on first run
    4. Use float (not int) for numbers that might have decimals later

    Example usage:
        if existing_table:
            # Table exists - check for duplicates and fetch incremental data
            existing_ids = {{row["id"] for row in existing_table.rows}}
            new_data = fetch_from_api()  # Your data source
            return [record for record in new_data if record["id"] not in existing_ids]
        else:
            # Fresh table - CRITICAL: Set schema correctly with first batch!
            return [
                {{"id": 1, "name": "Example", "created": "2024-01-01"}},
                {{"id": 2, "name": "Another", "created": "2024-01-02"}},
            ]
    """
    # TODO: Implement your data fetching logic here
    # This could be:
    # - API calls (requests.get, etc.)
    # - File reading (CSV, JSON, XML, etc.)
    # - Database queries (from other sources)
    # - Web scraping (BeautifulSoup, Scrapy, etc.)
    # - Any other data source

    return [
        # Example data showing proper types for schema inference:
        {{
            "id": 1,                           # int → INTEGER (good for primary keys)
            "title": "Example Title",          # str → TEXT
            "score": 85.5,                     # float → REAL (use float even for whole numbers!)
            "view_count": 100,                 # int → INTEGER
            "is_published": True,              # bool → INTEGER (0/1)
            "created_date": "2024-01-15",      # str → TEXT (ISO date format recommended)
            "tags": ["news", "technology"],    # list → TEXT (stored as JSON)
            "metadata": {{"priority": "high"}}, # dict → TEXT (stored as JSON)
        }},
        # Add more example records with same structure...
    ]


def transform_data(raw_data):
    """
    Optional: Transform/clean the raw data before database insertion.

    Args:
        raw_data: The data returned from fetch_data()

    Returns:
        List[Dict[str, Any]]: Transformed data

    Examples:
        # Clean strings
        for item in raw_data:
            item['name'] = item['name'].strip().title()

        # Parse dates
        for item in raw_data:
            item['created_date'] = datetime.fromisoformat(item['date_string'])

        # Handle complex data (sqlite-utils stores as JSON)
        for item in raw_data:
            item['metadata'] = {{"tags": ["news", "tech"], "priority": 1}}
    """
    # TODO: Add any data transformation logic here
    return raw_data


# TODO: Add any helper functions your project needs
# Examples:
# - API client functions
# - Data parsing utilities
# - Validation functions
# - Custom data transformation functions
'''

    def _generate_fragments_fallback(self, resource_name: str) -> str:
        """Generate fragments resource template using string formatting."""
        fragments_table = f"{resource_name}_fragments"

        return f'''"""
{resource_name.replace('_', ' ').title()} resource with fragments support for large documents.

This module implements TWO tables:
1. '{resource_name}' - Main table (schema determined by your fetch_data function)
2. '{fragments_table}' - Fragments table (schema determined by your fetch_fragments_data function)

IMPORTANT: You define both table schemas through your returned data structure.
Zeeker does not enforce any specific field names or relationships.

The database is built using sqlite-utils with automatic schema detection.
"""


def fetch_data(existing_table):
    \"\"\"
    Fetch data for the {resource_name} table.

    Args:
        existing_table: sqlite-utils Table object if table exists, None for new table
                       Use this to check for existing data and avoid duplicates

    Returns:
        List[Dict[str, Any]]: Records for the main table

    IMPORTANT - Schema Considerations:
    Your FIRST fetch_data() call determines the column types permanently!
    sqlite-utils infers types from the first ~100 records and locks them in.

    You have complete freedom to define your schema. Common patterns:
    - Simple: {{"id": 1, "title": "Doc 1", "content": "..."}}
    - Metadata focused: {{"id": 1, "title": "Doc 1", "source": "...", "date": "..."}}
    - Complex: {{"id": 1, "title": "Doc 1", "metadata": {{"tags": ["tag1"]}}, "status": "active"}}
    \"\"\"
    # TODO: Implement your data fetching logic
    # This is just an example - replace with your actual schema and data
    return [
        {{
            "id": 1,                              # Required: some kind of identifier
            "title": "Example Document",          # Your field names and types
            "content": "Document content...",     # You decide what goes in main vs fragments
            # Add any other fields your project needs
        }},
        # Add more records...
    ]


def fetch_fragments_data(existing_fragments_table):
    \"\"\"
    Fetch fragments data for the {fragments_table} table.

    This is called automatically after fetch_data().

    Args:
        existing_fragments_table: sqlite-utils Table object if exists, None for new table
                                 Use this to check existing fragments and avoid duplicates

    Returns:
        List[Dict[str, Any]]: Fragment records with YOUR chosen schema

    IMPORTANT: You have complete freedom to define the fragments schema.
    Common patterns include:

    1. Simple text chunks:
       {{"parent_id": 1, "text": "fragment content"}}

    2. Positional fragments:
       {{"doc_id": 1, "position": 0, "content": "...", "length": 500}}

    3. Semantic fragments:
       {{"document_id": 1, "section_type": "intro", "text": "...", "page": 1}}

    4. Custom fragments:
       {{"source_id": 1, "fragment_data": "...", "metadata": {{"type": "citation"}}}}

    The only requirement: some way to link fragments back to main records.
    \"\"\"
    # TODO: Implement your fragments logic
    # This is just an example - replace with your actual implementation

    # Example 1: Simple approach - split content from main table
    example_text = \"\"\"
    This is an example document that will be split into fragments.
    You can implement any splitting logic you need.

    Maybe you want sentence-based fragments, paragraph-based,
    or even semantic chunks based on document structure.

    The choice is entirely yours based on your project needs.
    \"\"\"

    # Your splitting logic goes here
    fragments = []
    sentences = example_text.split('.')
    for i, sentence in enumerate(sentences):
        if sentence.strip():
            fragments.append({{
                "parent_id": 1,                   # Link to main table (your choice of field name)
                "sequence": i,                    # Your choice of ordering
                "text": sentence.strip(),         # Your choice of content field name
                # Add any other fields your fragments need
            }})

    return fragments


def transform_data(raw_data):
    \"\"\"
    Optional: Transform main table data before database insertion.

    Args:
        raw_data: The data returned from fetch_data()

    Returns:
        List[Dict[str, Any]]: Transformed data
    \"\"\"
    # TODO: Add any data transformation logic here
    return raw_data


def transform_fragments_data(raw_fragments):
    \"\"\"
    Optional: Transform fragment data before database insertion.

    Args:
        raw_fragments: The data returned from fetch_fragments_data()

    Returns:
        List[Dict[str, Any]]: Transformed fragment data
    \"\"\"
    # TODO: Add any fragment processing logic here
    return raw_fragments


# TODO: Add any helper functions your project needs
# Examples:
# - Document parsing functions
# - Text splitting utilities
# - Data validation functions
# - API client functions
'''
