# AI Surveillance Engine

A high-performance, multi-process AI Face Recognition Surveillance Engine designed for constrained hardware. Built on FastAPI, Redis Streams, and PostgreSQL.

## Features
- **Real-Time Tracking**: Uses YuNet + ByteTracker for lightning-fast multi-face tracking.
- **Microservice Architecture**: Fully decoupled via Redis Streams for horizontal scaling.
- **Smart Cooldowns**: Avoids spamming the database with duplicate sightings of the same person.
- **REST API**: Centralized administration for suspect enrollment and evidence retrieval.

## System Requirements
- Python 3.11+
- PostgreSQL 14+ (with `pgvector` extension)
- Redis 5+ (or Memurai for Windows)
- 8GB RAM minimum.

## Setup Instructions

### 1. Environment Configuration
Copy the template file to create your environment variables:
```bash
cp .env.example .env
```
Edit `.env` and fill in your Database credentials and specify a secure `API_KEY`. If `API_KEY` is left blank, the system will run in Developer Mode (authentication disabled).

### 2. Install Dependencies
Using Poetry (Recommended):
```bash
poetry install
```
Or via pip:
```bash
pip install -r requirements.txt
```

### 3. Database Initialization
Ensure PostgreSQL is running and the database matches your `.env` settings. Run Alembic migrations to build the schema:
```bash
alembic upgrade head
```

### 4. Running the System
The system relies on an Orchestrator pattern. A single script will launch the FastAPI backend, the AI Brain (Recognition Worker), and edge node listeners (Camera Workers).

```bash
python run_all.py
```
To safely shut down the system without corrupting data or leaving zombie processes, press `Ctrl+C`. The orchestrator will send a termination signal to all workers and gracefully close connections.

## Architecture & Integration
For a deep dive into how to integrate external systems, listen to real-time WebSockets/Streams, and utilize the REST API, please see [`dc/INTEGRATION_GUIDE.md`](dc/INTEGRATION_GUIDE.md).
