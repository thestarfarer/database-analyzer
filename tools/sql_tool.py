"""
SQL Execution Tool - Database Query Interface for LLM

This tool provides the LLM with the ability to execute SQL queries against
the configured database. It handles query execution, result formatting,
error handling, and logging for analysis purposes.

Key Features:
- MSSQL-specific syntax support (TOP, GETDATE(), etc.)
- Configurable result limit to prevent overwhelming LLM context
- Automatic JSON encoding/decoding for complex queries
- Verbose execution logging for debugging
- Error recovery and user feedback
"""

from qwen_agent.tools.base import BaseTool
import json
import time
from datetime import datetime
from database.connection import DatabaseConnection


class ExecuteSQLTool(BaseTool):
    name = "execute_sql"
    parameters = [{'query': 'MSSQL query'}]

    def __init__(self, db_connection: DatabaseConnection, verbose: bool = True):
        self.db_connection = db_connection
        self.verbose = verbose

    @property
    def description(self):
        """Dynamic description that includes the actual result limit."""
        return f"""Execute SQL queries on MSSQL database and return formatted results.
    Double quotes in strings do not need to be escaped. (Column = 'Value "with quotes"' is the correct syntax)
    Use MSSQL syntax standards: TOP instead of LIMIT, GETDATE() instead of NOW(), etc.
    SQL responses are limited to {self.db_connection.result_limit} rows. Remaining rows will be truncated."""

    def call(self, query: str = None, **kwargs) -> str:
        if query is None:
            query = kwargs.get('query')

        if not query:
            return "Error: No SQL query provided"

        # Handle JSON-encoded queries
        query = str(query).strip()
        if query.startswith('{"query":'):
            try:
                parsed = json.loads(query)
                query = parsed['query']
            except json.JSONDecodeError:
                return "Error: Invalid JSON query format"

        return self._execute_query_internal(query)
    
    def _execute_query_internal(self, query: str) -> str:
        """Internal method for executing SQL query."""
        # Console logging for verbose mode
        if self.verbose:
            self._log_sql_execution_start(query)

        # Execute query with timing
        start_time = time.time()
        result = self.db_connection.execute_query(query)
        execution_time = time.time() - start_time

        if self.verbose:
            self._log_sql_execution_end(result, execution_time)

        return result
    
    def _log_sql_execution_start(self, query: str):
        """Log SQL query execution start with formatted output."""
        print("\n" + "="*80)
        print(f"🔍 SQL QUERY EXECUTION - {datetime.now().strftime('%H:%M:%S')}")
        print("="*80)
        
        # Format SQL query for better readability
        formatted_query = self._format_sql_query(query)
        print("📝 Query:")
        print("-" * 40)
        print(formatted_query)
        print("-" * 40)
    
    def _log_sql_execution_end(self, result: str, execution_time: float):
        """Log SQL query execution end with results."""
        print(f"⏱️  Execution Time: {execution_time:.3f} seconds")
        print("\n📊 Database Response:")
        print("-" * 40)
        
        # Show complete results (same as what LLM sees)
        print(result)
        
        print("-" * 40)
        print("✅ Query execution completed")
        print("="*80 + "\n")
    
    def _format_sql_query(self, query: str) -> str:
        """Basic SQL formatting for better readability."""
        # Simple formatting - add indentation for common SQL keywords
        keywords = ['SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'HAVING', 'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN']
        
        formatted = query.strip()
        for keyword in keywords:
            formatted = formatted.replace(f' {keyword} ', f'\n{keyword} ')
            formatted = formatted.replace(f' {keyword.lower()} ', f'\n{keyword} ')
        
        # Clean up extra newlines and add indentation
        lines = [line.strip() for line in formatted.split('\n') if line.strip()]
        formatted_lines = []
        
        for line in lines:
            if any(line.upper().startswith(kw) for kw in keywords):
                formatted_lines.append(line)
            else:
                formatted_lines.append(f"    {line}")
        
        return '\n'.join(formatted_lines)

