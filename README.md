# Item Processing Service

A production-oriented FastAPI service demonstrating safe concurrent processing, database row locking, idempotency, transaction management, and automated concurrency testing.

The project was designed around a common real-world API reliability problem:

> What happens when multiple requests try to process the same item at the same time, or when a client retries the same request because of a network failure?

This project demonstrates how to prevent duplicate business processing using PostgreSQL transactions, `SELECT FOR UPDATE`, database constraints, idempotency keys, and automated tests.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Race Condition](#race-condition)
- [Solution](#solution)
- [Architecture](#architecture)
- [Transaction Flow](#transaction-flow)
- [Idempotency](#idempotency)
- [Database Design](#database-design)
- [Testing Strategy](#testing-strategy)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [API Examples](#api-examples)
- [Engineering Decisions](#engineering-decisions)
- [Current Status](#current-status)
- [Future Improvements](#future-improvements)
- [Interview Explanation](#interview-explanation)

---

## Problem Statement

Imagine an API that performs an expensive business operation:

```http
POST /items/{item_id}/process
```

An item initially has:

```text
PENDING
```

and after successful processing:

```text
COMPLETED
```

A naive implementation might:

```text
1. Read item
2. Check status
3. Process item
4. Mark item COMPLETED
```

This looks correct, but it is vulnerable to concurrent requests.

---

## Race Condition

Two requests can arrive at almost the same time:

```text
Request A                     Request B
    |                             |
    v                             v
Read item                    Read item
    |                             |
    v                             v
PENDING                       PENDING
    |                             |
    v                             v
Process                       Process
    |                             |
    v                             v
COMPLETED                    COMPLETED
```

The same item can therefore be processed twice.

### Race Condition Reproduced

Before introducing locking, the project deliberately reproduced the problem using two independent database sessions.

Example output:

```text
PROCESSING ITEM 1 COUNT=1
PROCESSING ITEM 1 COUNT=2
```

This provided an automated demonstration of the race condition instead of relying on assumptions.

---

## Solution

The service uses two complementary reliability mechanisms.

### 1. Database Row Locking

The processing operation uses PostgreSQL row-level locking through SQLAlchemy:

```python
.with_for_update()
```

Conceptually, this executes:

```sql
SELECT *
FROM items
WHERE id = 1
FOR UPDATE;
```

The row remains locked until the transaction commits or rolls back.

### 2. Idempotency Keys

Clients can send:

```http
Idempotency-Key: abc-123
```

The service stores the key and request information in PostgreSQL.

For a retry:

```text
Same Idempotency-Key
        +
Same Request
        |
        v
Return previous result
```

If the same key is reused for a different request:

```text
Same Idempotency-Key
        +
Different Request
        |
        v
409 Conflict
```

---

## Architecture

```text
                         Client
                           |
                           |
                           v
                    +-------------+
                    |   FastAPI   |
                    +------+------+
                           |
                           | Idempotency-Key
                           v
                +----------------------+
                | Idempotency Service  |
                +----------+-----------+
                           |
                           v
                +----------------------+
                |     PostgreSQL       |
                | idempotency_records  |
                +----------+-----------+
                           |
                           v
                  SELECT FOR UPDATE
                           |
                           v
                    +-------------+
                    |    Items    |
                    +------+------+
                           |
                           v
                  Business Processing
                           |
                           v
                +----------------------+
                | processing_records   |
                +----------------------+
```

---

## Transaction Flow

The critical processing operation runs inside a database transaction:

```text
BEGIN TRANSACTION
       |
       v
SELECT item FOR UPDATE
       |
       v
Acquire row lock
       |
       v
Check item status
       |
       v
Create processing record
       |
       v
Execute business operation
       |
       v
Mark item COMPLETED
       |
       v
Store idempotency response
       |
       v
COMMIT
```

The important principle is:

> The row lock must remain active throughout the critical business operation.

We therefore avoid committing immediately after changing the item to `PROCESSING`.

---

## Idempotency

For a request such as:

```http
POST /items/10/process
Idempotency-Key: test-key-001
```

the service generates a deterministic request hash.

Conceptually:

```text
item_id = 10
    |
    v
Request Hash
    |
    v
Idempotency Record
```

The database stores:

```text
idempotency_key
item_id
request_hash
status
response
created_at
```

A database-level unique constraint is also used:

```text
UNIQUE(idempotency_key)
```

### First Request

```text
Client
  |
  | Idempotency-Key: ABC123
  v
No existing key
  |
  v
Process item
  |
  v
COMPLETED
  |
  v
Store response
  |
  v
Return 200
```

### Retry Request

```text
Client
  |
  | Same Idempotency-Key
  v
Existing record
  |
  v
Validate request hash
  |
  v
Return stored response
```

The business operation is not executed again.

### Idempotency Key Reuse

First request:

```http
Idempotency-Key: ABC123
```

```json
{
  "item_id": 10
}
```

Second request:

```http
Idempotency-Key: ABC123
```

```json
{
  "item_id": 20
}
```

The same key is associated with a different request, so the service returns:

```text
409 Conflict
```

---

## Database Design

### `items`

Stores the business entity.

```text
id
name
amount
status
created_at
updated_at
```

Possible statuses:

```text
PENDING
PROCESSING
COMPLETED
FAILED
```

### `processing_records`

Tracks actual business-processing attempts.

```text
id
item_id
status
created_at
```

This table helps answer:

> How many times was this item actually processed?

For a correctly protected operation:

```text
item_id = 10

processing_records

id | item_id | status
---+---------+--------
1  |   10    | SUCCESS
```

### `idempotency_records`

Tracks client requests.

```text
id
idempotency_key
item_id
request_hash
status
response
created_at
```

The database enforces:

```text
UNIQUE(idempotency_key)
```

This provides a database-level guarantee against duplicate idempotency keys.

---

## Testing Strategy

The project uses `pytest` with PostgreSQL integration/concurrency testing.

Current test suite:

```text
tests/test_items.py
tests/test_concurrency.py
tests/test_idempotency.py
```

Current status:

```text
4 passed
```

### Test 1 — Create Item

Verifies that an item can be created successfully.

```text
POST /items
      |
      v
Item created
      |
      v
PENDING
```

### Test 2 — Database Isolation

Ensures test data does not leak between tests.

This is particularly important because the application uses real PostgreSQL transactions and independent database sessions.

### Test 3 — Concurrent Processing

Two independent database sessions attempt to process the same item concurrently.

Expected invariant:

```text
2 requests
    |
    v
1 processing operation
    |
    v
SUCCESS
    |
    v
COMPLETED
```

The test verifies:

```text
processing_records = 1
item.status = COMPLETED
processing.status = SUCCESS
```

### Test 4 — Concurrent Idempotency

Two concurrent requests use the same idempotency key.

The test verifies:

```text
2 requests
      |
      v
same idempotency key
      |
      v
1 idempotency record
      |
      v
1 processing operation
```

---

## Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.13 | Application language |
| FastAPI | REST API |
| PostgreSQL | Primary database |
| SQLAlchemy | ORM / database access |
| Alembic | Database migrations |
| Pytest | Automated testing |
| Psycopg | PostgreSQL driver |
| Docker | Local PostgreSQL environment |

---

## Project Structure

```text
item-processing-service/
├── app/
│   ├── api/
│   │   └── items.py
│   ├── models/
│   │   ├── item.py
│   │   ├── processing.py
│   │   └── idempotency.py
│   ├── services/
│   │   ├── item_processor.py
│   │   └── idempotency.py
│   ├── database.py
│   └── main.py
│
├── migrations/
│   └── versions/
│
├── tests/
│   ├── conftest.py
│   ├── test_items.py
│   ├── test_concurrency.py
│   └── test_idempotency.py
│
├── docker-compose.yml
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## Getting Started

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd item-processing-service
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
```

Activate it:

#### macOS / Linux

```bash
source .venv/bin/activate
```

#### Windows

```powershell
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start PostgreSQL

If PostgreSQL is configured through Docker:

```bash
docker compose up -d
```

Verify:

```bash
docker ps
```

### 5. Run database migrations

```bash
alembic upgrade head
```

Check the migration:

```bash
alembic current
```

### 6. Start the API

```bash
uvicorn app.main:app --reload
```

API:

```text
http://127.0.0.1:8000
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

---

## Running Tests

Run all tests:

```bash
pytest -v
```

Run the concurrency test:

```bash
pytest -v tests/test_concurrency.py -s
```

Run the idempotency test:

```bash
pytest -v tests/test_idempotency.py -s
```

---

## API Examples

### Create Item

```http
POST /items
Content-Type: application/json
```

Request:

```json
{
  "name": "Laptop",
  "amount": 85000
}
```

Example response:

```json
{
  "id": 1,
  "name": "Laptop",
  "amount": 85000,
  "status": "PENDING"
}
```

### Process Item

```http
POST /items/1/process
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
```

Example response:

```json
{
  "item_id": 1,
  "status": "COMPLETED",
  "message": "Item processed successfully"
}
```

---

## Engineering Decisions

### Why PostgreSQL locking?

The item state is stored in PostgreSQL, and PostgreSQL provides transactional row-level locking.

Using:

```python
.with_for_update()
```

allows the database to coordinate concurrent transactions.

### Why not use a Python lock?

A Python:

```python
threading.Lock()
```

only protects memory inside one application process.

It is not sufficient when running:

```text
Multiple API workers
Multiple containers
Kubernetes pods
Multiple servers
```

A database lock provides coordination across application instances sharing the same database.

### Why use a database UNIQUE constraint?

Application logic such as:

```python
if not exists:
    insert()
```

is vulnerable to concurrent requests.

The database constraint:

```text
UNIQUE(idempotency_key)
```

provides the final guarantee.

### Why use request hashing?

An idempotency key identifies a logical request.

Without a request hash, a client could send:

```text
Key: ABC
Item: 10
```

followed by:

```text
Key: ABC
Item: 20
```

The request hash detects that mismatch and allows the API to reject it with:

```text
409 Conflict
```

---

## Current Status

```text
✅ FastAPI application
✅ PostgreSQL integration
✅ SQLAlchemy models
✅ Alembic migrations
✅ Item creation
✅ Item processing
✅ Race condition reproduced
✅ Row-level locking implemented
✅ Idempotency keys implemented
✅ Request hash validation
✅ 409 conflict handling
✅ Concurrent processing tests
✅ Idempotency tests
✅ Database isolation
✅ 4 tests passing
```

---

## Future Improvements

The current implementation is a proof of concept focused on concurrency and idempotency.

Potential production enhancements include:

- Redis-based distributed caching
- Background workers
- Kafka/RabbitMQ integration
- Retry policies
- Dead-letter queues
- Processing timeout and recovery
- Stuck `PROCESSING` item recovery
- Structured logging
- Prometheus metrics
- OpenTelemetry tracing
- Authentication and authorization
- Rate limiting
- API versioning
- Circuit breakers
- Kubernetes deployment
- CI/CD pipeline
- Load testing
- Horizontal scaling
- Idempotency record expiration and cleanup

---

## Interview Explanation

A concise way to explain the project:

> I built a FastAPI-based item processing service to reproduce and solve a concurrency problem. Initially, two concurrent requests could read the same item as `PENDING` and both execute the business operation. I reproduced the issue using independent SQLAlchemy sessions and concurrency tests.
>
> I solved the problem by moving the critical operation into a single database transaction and using PostgreSQL row-level locking with `SELECT FOR UPDATE`. I then added idempotency keys to protect against client retries and stored a request hash to detect reuse of the same key with a different request.
>
> I also added database-level unique constraints and automated tests covering normal processing, database isolation, concurrent processing, and concurrent idempotent requests. The test suite currently passes all four tests.

---

## Learning Outcomes

This project demonstrates practical understanding of:

- REST API design
- FastAPI
- PostgreSQL
- SQLAlchemy
- Database transactions
- Transaction boundaries
- Row-level locking
- Race-condition analysis
- Idempotency
- Database constraints
- Request hashing
- Concurrent processing
- Pytest
- Integration testing
- Database migrations
- Test isolation
- Failure prevention


