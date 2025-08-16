# CLAUDE.md

## Commands
- `uv run pytest [-m unit|integration|cli]` `uv run black .` 
- `uv run zeeker init|add|build|deploy` `--fragments --async --sync-from-s3 --force-schema-reset`
- `uv run zeeker build [resource1] [resource2]` (selective building)
- `uv run zeeker assets generate|validate|deploy`

## Architecture
CLI tool: database projects (init→add→build→deploy) + UI assets (generate→validate→deploy)
S3 three-pass: Database files → base assets → database-specific customizations
Fragments: main table (metadata) + fragments table (searchable chunks)
Safety: Template validation, CSS scoping `[data-database="name"]`

## Structure
```
project/{pyproject.toml,zeeker.toml,resources/resource_name.py,project_name.db,metadata.json}
```

## Functions
`fetch_data(existing_table)` → List[Dict] (existing_table=Table|None, filter duplicates)
`async fetch_data(existing_table)` (concurrent I/O)
`fetch_fragments_data(existing_fragments_table, main_data_context=None)` (main_data_context avoids duplicate API calls)
`transform_data()` (optional)

## CRITICAL: Duplicate Handling
MUST filter existing IDs to avoid UNIQUE constraint errors:
```python
def fetch_data(existing_table):
    data = get_fresh_data()
    if existing_table:
        existing_ids = {row["id"] for row in existing_table.rows}
        data = [item for item in data if item["id"] not in existing_ids]
    return data
```
Time-based: `existing_table.db["_zeeker_updates"].get(table_name)["last_updated"]`
Fixes: Delete .db file or `--force-schema-reset`

## Async
`--async` for concurrent I/O (100 sequential calls = ~100s, concurrent = ~5-10s)

## Schema
Meta tables: `_zeeker_schemas` (versions), `_zeeker_updates` (timestamps, counts)
Type inference locks on first batch: int→INTEGER, float→REAL, str→TEXT, bool→INTEGER, list/dict→JSON
Schema conflicts: Add `migrate_schema()`, use `--force-schema-reset`, or delete .db
CRITICAL: Use `float` for potential decimals, consistent types, no type mixing

## Fragments
`--fragments`: Two tables (main: metadata, fragments: chunks). Context passing via `main_data_context` avoids duplicate API calls.
```python
def fetch_fragments_data(existing_fragments_table, main_data_context=None):
    if main_data_context:
        return [{"parent_id": doc["id"], "text": chunk} 
                for doc in main_data_context for chunk in split_document(doc["content"])]
```
Search: `WHERE fragments_table.text MATCH 'terms'`

## S3 & Environment
Three-pass: Database files → base assets → database customizations
Template safety: ❌ Banned `database.html,table.html,index.html,query.html` ✅ Safe `database-{DBNAME}.html,custom-*.html`
Env (auto-loads `.env`): `S3_BUCKET,AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY,JINA_API_TOKEN,OPENAI_API_KEY`

## Testing
Markers: `unit,integration,cli,slow` (`pytest -m marker`)

## Selective Building
`zeeker build users posts` (builds specific resources)
`zeeker build` (builds all resources)

## Code Recipes
```python
# Jina Reader (web extraction)
@retry(stop=stop_after_attempt(3))
async def get_jina_reader_content(link: str) -> str:
    headers = {"Authorization": f"Bearer {os.environ.get('JINA_API_TOKEN')}"}
    async with httpx.AsyncClient(timeout=90) as client:
        return (await client.get(f"https://r.jina.ai/{link}", headers=headers)).text

# Hash IDs (deterministic from multiple fields)
def get_hash_id(elements: list[str]) -> str:
    return hashlib.md5("|".join(str(e) for e in elements).encode()).hexdigest()

# OpenAI summarization
async def get_summary(text: str) -> str:
    client = AsyncOpenAI(max_retries=3, timeout=60)
    response = await client.responses.create(model="gpt-4o-mini", 
        input=[{"role": "system", "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]},
               {"role": "user", "content": [{"type": "input_text", "text": f"Summarize:\n{text}"}]}])
    return response.output_text
```