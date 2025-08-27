"""
Database Module
"""

import asyncio
import sqlite3
from collections.abc import AsyncIterator
from concurrent.futures.thread import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Callable, LiteralString, ParamSpec, TypeVar

from fastapi import Request
import logfire
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter

P = ParamSpec("P")
R = TypeVar("R")
THIS_DIR = Path(__file__).parent


@dataclass
class Database:
    """Rudimentary database to store chat messages in SQLite.

    The SQLite standard library package is synchronous, so we
    use a thread pool executor to run queries asynchronously.
    """

    con: sqlite3.Connection
    _loop: asyncio.AbstractEventLoop
    _executor: ThreadPoolExecutor

    @classmethod
    @asynccontextmanager
    async def connect(
        cls, file: Path = THIS_DIR / ".chat_app_messages.sqlite"
    ) -> AsyncIterator["Database"]:
        """
        Asynchronously connects to a SQLite database and provides an asynchronous
        context manager for database operations.

        Args:
            file (Path, optional): The path to the SQLite database file. Defaults to
                a file named '.chat_app_messages.sqlite' in the current directory.

        Yields:
            AsyncIterator[Database]: An instance of the `Database` class for
            performing database operations.

        Raises:
            Exception: Propagates any exceptions raised during the connection or
            disconnection process.

        Notes:
            - This method uses a thread pool executor to offload the synchronous
              database connection to a separate thread.
            - The database connection is automatically closed when exiting the
              context manager.
        """
        with logfire.span("connect to DB"):
            loop = asyncio.get_event_loop()
            executor = ThreadPoolExecutor(max_workers=1)
            con = await loop.run_in_executor(executor, cls._connect, file)
            slf = cls(con, loop, executor)
        try:
            yield slf
        finally:
            await slf._asyncify(con.close)

    @staticmethod
    def _connect(file: Path) -> sqlite3.Connection:
        """
        Establishes a connection to the SQLite database file, instruments the connection
        with additional logging, and ensures the existence of a 'messages' table.

        Args:
            file (Path): The path to the SQLite database file.

        Returns:
            sqlite3.Connection: A connection object to the SQLite database.

        Side Effects:
            - Creates a 'messages' table in the database if it does not already exist.
            - Commits the creation of the table to the database.

        Notes:
            - The 'messages' table contains two columns:
                - id (INT): The primary key for the table.
                - message_list (TEXT): A text field to store message data.
        """
        con = sqlite3.connect(str(file))
        con = logfire.instrument_sqlite3(con)
        cur = con.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS messages (id INT PRIMARY KEY, message_list TEXT);"
        )
        con.commit()
        return con

    async def add_messages(self, messages: bytes):
        """
        Asynchronously adds a list of messages to the database.

        This method inserts the provided messages into the `messages` table
        and commits the transaction.

        Args:
            messages (bytes): A serialized list of messages to be added to the database.

        Raises:
            Exception: If the database operation fails.
        """
        await self._asyncify(
            self._execute,
            "INSERT INTO messages (message_list) VALUES (?);",
            messages,
            commit=True,
        )
        await self._asyncify(self.con.commit)

    async def get_messages(self) -> list[ModelMessage]:
        """
        Asynchronously retrieves a list of messages from the database.

        This method executes a SQL query to fetch all message lists from the
        "messages" table, ordered by their ID. Each message list is then
        deserialized into `ModelMessage` objects using the `ModelMessagesTypeAdapter`.

        Returns:
            list[ModelMessage]: A list of `ModelMessage` objects representing the
            messages retrieved from the database.
        """
        c = await self._asyncify(
            self._execute, "SELECT message_list FROM messages order by id"
        )
        rows = await self._asyncify(c.fetchall)
        messages: list[ModelMessage] = []
        for row in rows:
            messages.extend(ModelMessagesTypeAdapter.validate_json(row[0]))
        return messages

    def _execute(
        self, sql: LiteralString, *args: Any, commit: bool = False
    ) -> sqlite3.Cursor:
        """
        Executes an SQL statement with optional arguments and returns the cursor.
        Args:
            sql (LiteralString): The SQL query to execute.
            *args (Any): Positional arguments to substitute into the SQL query.
            commit (bool, optional): Whether to commit the transaction after executing
                the query. Defaults to False.
        Returns:
            sqlite3.Cursor: The cursor object after executing the query.
        Raises:
            sqlite3.Error: If an error occurs during the execution of the SQL query.
        """
        cur = self.con.cursor()
        cur.execute(sql, args)
        if commit:
            self.con.commit()
        return cur

    async def _asyncify(
        self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs
    ) -> R:
        """
        Asynchronously execute a synchronous function in a separate thread.

        This method uses an executor to run the provided synchronous function
        (`func`) in a thread pool, allowing it to be awaited in an asynchronous
        context.

        Args:
            func (Callable[P, R]): The synchronous function to be executed.
            *args (P.args): Positional arguments to pass to the function.
            **kwargs (P.kwargs): Keyword arguments to pass to the function.

        Returns:
            R: The result of the function execution.

        Raises:
            Any exception raised by the provided function will be propagated.

        Note:
            This method is useful for integrating blocking I/O-bound operations
            into an asynchronous workflow.
        """
        return await self._loop.run_in_executor(  # type: ignore
            self._executor,
            partial(func, **kwargs),
            *args,  # type: ignore
        )


async def get_db(request: Request) -> Database:
    """
    Retrieve the database instance from the request state.

    This function is an asynchronous dependency that extracts the `db` attribute
    from the `state` object of the provided `Request`. It is typically used in
    FastAPI applications to access the database connection associated with the
    current request.

    Args:
        request (Request): The HTTP request object containing the state.

    Returns:
        Database: The database instance stored in the request state.
    """
    return request.state.db
