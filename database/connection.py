"""
Database Connection Layer

Provides abstract database interface with MSSQL implementation.
Handles connection management, query execution, and result formatting
for the Database Analyzer system.
"""

from abc import ABC, abstractmethod
import pymssql
import logging
import time
from datetime import datetime
from config.settings import DatabaseConfig


class DatabaseConnection(ABC):
    """Abstract base for database connections."""
    @abstractmethod
    def execute_query(self, query: str) -> str:
        pass
    
    @abstractmethod
    def close(self):
        pass


class MSSQLConnection(DatabaseConnection):
    """MSSQL implementation with connection pooling and logging."""

    def __init__(self, config: DatabaseConfig, verbose: bool = True, result_limit: int = 100):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.verbose = verbose
        self.result_limit = result_limit
        self._connection = None
        self._query_count = 0
        self._total_execution_time = 0.0
        self._connect()
    
    def _connect(self):
        try:
            self._connection = pymssql.connect(
                server=self.config.server,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
                charset=self.config.charset
            )
            self.logger.info("Database connection established")
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            raise
    
    def execute_query(self, query: str) -> str:
        if not self._connection:
            self._connect()
        
        start_time = time.time()
        
        try:
            if self.verbose:
                self._log_db_operation_start(query)
            
            cursor = self._connection.cursor()
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            results = cursor.fetchall()
            cursor.close()

            execution_time = time.time() - start_time
            self._query_count += 1
            self._total_execution_time += execution_time

            if not columns or not results:
                result = "No results returned"
            else:
                # Format results as table
                table = " | ".join(columns) + "\n" + "-" * (len(" | ".join(columns))) + "\n"
                for row in results[:self.result_limit]:  # limit output
                    table += " | ".join(str(val) for val in row) + "\n"
                if len(results) > self.result_limit:
                    table += f"... ({len(results)-self.result_limit} more rows)\n"
                result = table
            
            if self.verbose:
                self._log_db_operation_end(result, execution_time, len(results) if results else 0)
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"Query execution failed: {e}")
            if self.verbose:
                self._log_db_operation_error(query, str(e), execution_time)
            return f"SQL execution error: {e}"
    
    def _log_db_operation_start(self, query: str):
        """Log database operation start."""
        print("\n" + "="*70)
        print(f"🗄️  DATABASE QUERY EXECUTION - {datetime.now().strftime('%H:%M:%S')}")
        print("="*70)
        print(f"🔗 Server: {self.config.server}")
        print(f"🗂️  Database: {self.config.database}")
        print(f"📊 Query #{self._query_count + 1}")
        print("-" * 70)
    
    def _log_db_operation_end(self, result: str, execution_time: float, row_count: int):
        """Log database operation end with metrics."""
        print(f"⏱️  Query Execution Time: {execution_time:.3f}s")
        print(f"📈 Rows Returned: {row_count}")
        print(f"📊 Session Stats: {self._query_count} queries, {self._total_execution_time:.3f}s total")
        
        # Show connection metrics
        avg_time = self._total_execution_time / self._query_count if self._query_count > 0 else 0
        print(f"⚡ Average Query Time: {avg_time:.3f}s")
        print("✅ Query executed successfully")
        print("="*70 + "\n")
    
    def _log_db_operation_error(self, query: str, error: str, execution_time: float):
        """Log database operation error."""
        print("\n" + "="*70)
        print(f"❌ DATABASE QUERY FAILED - {datetime.now().strftime('%H:%M:%S')}")
        print("="*70)
        print(f"🔗 Server: {self.config.server}")
        print(f"🗂️  Database: {self.config.database}")
        print(f"⏱️  Execution Time: {execution_time:.3f}s")
        print(f"🚨 Error: {error}")
        print("="*70 + "\n")

    def close(self):
        if self._connection:
            self._connection.close()
            self._connection = None