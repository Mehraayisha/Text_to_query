# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
Prompt templates for MongoDB query generation.

Contains templates for selector, refiner, and output parser prompts.
"""

from datetime import datetime
from typing import Dict, Any


def get_current_date() -> str:
    """Get current date in YYYY-MM-DD format"""
    return datetime.now().strftime("%Y-%m-%d")


def build_selector_prompt(
    context: str, fk_str: str, question: str, evidence: str, metrics: str, verified_queries: str
) -> str:
    """
    Build the MongoDB selector prompt for query generation.

    Args:
        context: Database schema/collection information
        fk_str: Relationship information
        question: User's question
        evidence: Custom instructions
        metrics: Available metrics
        verified_queries: Pre-verified query examples

    Returns:
        Formatted prompt string
    """
    current_date = get_current_date()

    template = """
You are a MongoDB expert and highly skilled MongoDB Query generator.

Your job is to analyze the user query and generate a MongoDB query following the schema and constraints provided.

⚠️ CRITICAL - YOU FREQUENTLY MAKE THIS MISTAKE:
You often write MongoDB queries with nested field errors that cause "unknown operator" failures.

🚨 UNIVERSAL RULE: ALL collection attributes must be treated as SEPARATE fields in MongoDB queries.

❌ WRONG: {{"companyName.value": "Cisco"}} - This creates unknown operator error!  
✅ CORRECT: {{"companyName": "Cisco"}} - companyName is a SEPARATE field, not nested!

 QUERY STRUCTURE REQUIREMENTS:
1. **JSON Balance**: Ensure every {{ has a matching }}, and every [ has a matching ].
2. **Proper Nesting**: All $group fields must be inside the $group object.
3. **Pipeline Stages**: Each $match, $group, $sort stage must be separate objects in an array.

🔥 CORRECT QUERY EXAMPLE:
Here is a COMPLETE example showing the EXACT format expected:

```json
{{
  "mongodb_query": "db.collection.aggregate([{{\\"$match\\":{{\\"field\\":\\"value\\"}},{{\\"$group\\":{{\\"_id\\":null,\\"count\\":{{\\"$sum\\":1}}}}])",
  "collection_name": "collection_name_here",
  "database_name": "database_name_here",
  "parameters": {{}},
  "entities": [{{"type": "collection", "name": "collection_name_here"}}],
  "query_type": "find_or_aggregate"
}}
```

⚠️ CRITICAL NOTES ON EXAMPLE:
- Notice the escaped quotes (\\\\") inside the mongodb_query string
- Notice the COMPACT format with NO spaces after {{ or before }} or around :
- Notice each pipeline stage is a separate object in the array
- Notice proper brace balance: every {{ has exactly one matching }}

🚨 AGGREGATION PIPELINE STRUCTURE:
✅ CORRECT: [{{"$match": {{...}}}}, {{"$group": {{...}}}}, {{"$sort": {{...}}}}]
❌ WRONG: [{{"$match": {{...}}, "$group": {{...}}}}] - Multiple operations in one stage!

🔥 CRITICAL $MATCH SYNTAX - PROPER CONDITION NESTING:
✅ CORRECT: {{"$match": {{"field1": "value1", "field2": "value2", "field3": {{"$gte": "value3"}}}}}}
❌ WRONG: {{"$match": {{"field1": "value1", "field2": "value2", "field3": {{"$gte": "value3"}}}}}} - Missing closing brace after nested condition!
⚠️  CRITICAL: ALL conditions in $match must be properly nested within the same object with correct brace closing

🔥 CRITICAL QUOTE AND DATE SYNTAX RULES:
✅ ALWAYS use DOUBLE QUOTES for all MongoDB operators, field names, and string values:
  - Field access: {{"field": "value"}}
  - Operators: {{"$match": {{...}}}}, {{"$group": {{...}}}}
  - Aggregation: {{"$sum": 1}}, {{"$avg": "$field"}}
  
❌ NEVER use single quotes in MongoDB query syntax:
  - WRONG: {{'$match': {{'field': 'value'}}}}
  - CORRECT: {{"$match": {{"field": "value"}}}}

� DATE HANDLING - ISODATE FUNCTION:
✅ CORRECT ISODate FORMAT: ISODate("YYYY-MM-DD") - Function with double quotes, date only
  - Example: ISODate("2023-10-20")
  - Calculate dates from CURRENT DATE: {current_date}
  
❌ FORBIDDEN DATE FORMATS:
  - Single quotes: ISODate('2023-10-20')
  - With timestamp: ISODate("2023-10-20T00:00:00.000Z")
  - Quoted function: "ISODate(\\"2023-10-20\\")"

✅ REQUIRED JSON OUTPUT FORMAT (with escaped double quotes):
"mongodb_query": "db.collection.aggregate([{{\\"$group\\": {{\\"_id\\": \\"$field\\", \\"count\\": {{\\"$sum\\": 1}}}}])"

🔥 CRITICAL JSON FORMATTING - COMPACT SYNTAX (NO EXTRA SPACES):
⚠️  YOU FREQUENTLY ADD EXTRA SPACES THAT BREAK MCP SERVICE PARSING!
✅ CORRECT COMPACT FORMAT (no spaces after {{ or before }}):
  - {{"$match":{{"field":"value"}}}}  ← Compact, no spaces
  - {{"$group":{{"_id":"$field","count":{{"$sum":1}}}}}}  ← Compact
  
❌ WRONG WITH SPACES (causes "pipeline must be a list of stages" error):
  - {{ "$match": {{ "field": "value" }} }}  ← Extra spaces break parsing!
  - {{ "$group": {{ "_id": "$field", "count": {{ "$sum": 1 }} }} }}  ← Fails!

🚨 BRACE COUNTING RULE: 
✅ Every opening {{ must have EXACTLY ONE matching closing }}
✅ Count braces carefully when nesting $dateToString, $sum, etc.
❌ COMMON ERROR: {{"$group":{{"_id":{{"$dateToString":{{...}}}},​"count":{{"$sum":1}}}}}}  ← Extra }} at end!
✅ CORRECT: {{"$group":{{"_id":{{"$dateToString":{{...}}}},​"count":{{"$sum":1}}}}}}  ← Balanced

💡 TIP: After writing query, mentally count opening/closing braces to ensure balance!

Context Rules:
- Use separate fields for non-nested attributes
- No nested field syntax for individual attributes

🔤 TEXT SEARCH:
- Case-insensitive: {{"field": {{"$regex": "pattern", "$options": "i"}}}}
- Exact match: {{"field": "exact_value"}}

📊 AGGREGATION:
- Use aggregation pipeline for complex queries
- Include $lookup for joins using ObjectId references
- Always include $project to limit returned fields

💡 OPTIMIZATION:
- ⚠️ CRITICAL FIND() LIMIT RULE: Always enforce a maximum of 100 documents on find() queries
  * If no .limit(...) is present, append .limit(100)
  * If a limit > 100 is present, change it to .limit(100)
  * If a limit ≤ 100 is present, keep it
  * Aggregation pipelines should include a $limit stage (≤ 100) when returning documents
- Use indexes when available
- Prefer find() for simple queries, aggregate() for complex ones

🔗 CRITICAL RELATIONSHIP JOINS - MULTI-STEP LOOKUPS:
⚠️  CRITICAL: When joining data across multiple collections, ALWAYS follow the relationship chain correctly:

🚨 CRITICAL ERROR PATTERN TO AVOID:
❌ WRONG: Directly joining collections that require bridge relationships
❌ WRONG: Skipping intermediate collections in relationship chains

✅ CORRECT: Always check [Relationships] section for proper join paths:
1. Identify direct relationships (one-step joins)
2. Identify bridged relationships (multi-step joins through intermediate collections)
3. Follow the exact relationship chain specified in the semantic model

🔥 RELATIONSHIP CHAIN RULE: Always check the [Relationships] section to understand the proper join path between collections!

IMPORTANT: Generate ONLY the MongoDB query. The semantic analysis has already been done.
CRITICAL: Your query MUST be syntactically complete and valid.

Ensure that the query is strictly relevant to the [Question], without any extraneous fields or calculations.
Highlight any assumptions made while generating the query.
Ensure the query is formatted for readability.

CURRENT DATE: {current_date}

==========
[Database schema]

{context}

[Relationships]
{fk_str}

[Question]
{question}

[Custom Instructions]
{evidence}

[Metrics]
{metrics}

[Verified Queries]
{verified_queries}

🚨 CRITICAL: Return ONLY valid JSON in this EXACT format:

```json
{{
  "mongodb_query": "your_mongodb_query_here",
  "collection_name": "collection_name_here",
  "database_name": "database_name_here",
  "parameters": {{}},
  "entities": [{{"type": "collection", "name": "collection_name_here"}}],
  "query_type": "find_or_aggregate"
}}
```

IMPORTANT:
- Use JSON format with ```json wrapper  
- Always use double quotes in JSON
- Never use JavaScript object format
- Include all required fields: mongodb_query, collection_name, database_name, parameters, entities, query_type
"""

    # Escape curly braces in ALL string variables to prevent format() from treating them as placeholders
    # Replace single { and } with double {{ and }} but preserve actual format placeholders
    context_escaped = context.replace("{", "{{").replace("}", "}}")
    fk_str_escaped = fk_str.replace("{", "{{").replace("}", "}}")
    verified_queries_escaped = verified_queries.replace("{", "{{").replace("}", "}}")
    evidence_escaped = evidence.replace("{", "{{").replace("}", "}}")
    metrics_escaped = metrics.replace("{", "{{").replace("}", "}}")

    return template.format(
        current_date=current_date,
        context=context_escaped,
        fk_str=fk_str_escaped,
        question=question,
        evidence=evidence_escaped,
        metrics=metrics_escaped,
        verified_queries=verified_queries_escaped,
    )


def build_refiner_prompt(
    query: str, desc_str: str, fk_str: str, sql: str, error: str, exception_class: str
) -> str:
    """
    Build the MongoDB refiner prompt for fixing query errors.

    Args:
        query: User's original question
        desc_str: Database schema information
        fk_str: Relationship information
        sql: Original MongoDB query that failed
        error: Error message from execution
        exception_class: Type of exception

    Returns:
        Formatted prompt string
    """
    template = """
【Instruction】
When executing MongoDB query below, some errors occurred, please fix up the MongoDB query based on question and database info.
Prioritize using the verified queries exactly as written — along with all their specified logic—when adapting or applying them to the given question if the verified query for the [Question] is available.
Otherwise solve the task step by step.
Using MongoDB query format in the code block, and indicate script type in the code block.
When you find an answer, verify the answer carefully. 
If no MongoDB query is found in [old MongoDB Query], do not generate new query, just return the [error] and [exception_class] as is.

【Constraints】
- In aggregation pipeline, select only needed fields in the 【Question】 without any unnecessary field or value
- Do not include unnecessary collections in $lookup operations
- If use $max or $min in $group, ensure proper $lookup operations FIRST, THEN use aggregation
- If field values indicate 'None' or null, use $match with proper null checks like {{"field": {{"$ne": null}}}}
- If use $sort in aggregation pipeline, ensure it comes after all necessary $match and $lookup operations
- Use proper ObjectId handling with ObjectId() constructor for _id field references
- Ensure proper date handling with ISODate() or appropriate date operators

【Query】
-- {query}

【Database info】
{desc_str}
【Relationships】
{fk_str}
【old MongoDB Query】
```json
{sql}
```
【error】 
{error}
【Exception class】
{exception_class}

Now please fix up old MongoDB Query and generate new MongoDB query again. 

🚨 CRITICAL: Return ONLY valid JSON in this EXACT format:

```json
{{
  "mongodb_query": "your_fixed_query_here",
  "collection_name": "collection_name_here",
  "database_name": "database_name_here", 
  "parameters": {{}},
  "entities": [],
  "query_type": "aggregate"
}}
```

IMPORTANT: 
- Use JSON format with ```json wrapper
- Keep the same collection_name and database_name from the old query
- Fix only the mongodb_query field with corrected syntax
- Always use double quotes in JSON
- Never use JavaScript object format

【correct MongoDB Query】
"""

    return template.format(
        query=query,
        desc_str=desc_str,
        fk_str=fk_str,
        sql=sql,
        error=error,
        exception_class=exception_class,
    )


def build_output_parser_prompt(user_query: str, query_result: str) -> str:
    """
    Build the output parser prompt for formatting results.

    Args:
        user_query: User's original question
        query_result: Raw query result data

    Returns:
        Formatted prompt string
    """
    template = """
You are an assistant that formats structured data results into clear, informative responses.
The user asked: {user_query}

Data to format: {query_result}

Format the response as follows:

For single values or simple responses:
- Present information in complete, descriptive sentences
- Include relevant identifiers (order numbers, IDs, etc.) from the original question
- Examples: "Yes, the order <ORDER_NUMBER> exists", "The order <ORDER_NUMBER> is on hold due to Item ANSSI Hold", "The status is ACTIVE"

For multiple values or list data:
- Use bullet points for better readability
- Each bullet point should contain one complete data item
- Remove technical formatting but preserve the actual content
- Example format:
  • Date and instruction entry 1
  • Date and instruction entry 2
  • Date and instruction entry 3

General rules:
- Remove database function syntax, column names, and technical formatting
- Present data values exactly as they appear without summarization
- If the data is empty, respond with "Apologies, I am unable to assist you with this right now."
- Do not add introductory phrases like "The results are" or "Here is the information"
- Make responses informative and user-friendly while staying factual

Response:
"""

    return template.format(user_query=user_query, query_result=query_result)
