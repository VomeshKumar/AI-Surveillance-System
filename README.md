# AI Face Recognition Surveillance System

![CI/CD](https://img.shields.io/badge/CI%2FCD-Pending-yellow)
![License](https://img.shields.io/badge/License-MIT-blue)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green?logo=fastapi)
![React](https://img.shields.io/badge/React-18-blue?logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5-blue?logo=typescript)

An advanced, real-time surveillance system that leverages AI for face detection and recognition. The system is designed with a scalable microservices architecture, providing a robust platform for monitoring, evidence management, and alerting.

## ✨ Key Features

- **Real-Time Face Detection:** High-performance face detection using the YUNet model.
- **Accurate Face Recognition:** Employs the GhostFaceNet model for accurate facial recognition against a watchlist.
- **Web-Based Dashboard:** A modern, responsive dashboard built with React, TypeScript, and Vite for system monitoring, user management, and viewing surveillance feeds.
- **Scalable Microservices Architecture:** Comprises distinct services for the AI engine, dashboard API, and background workers, ensuring scalability and maintainability.
- **Evidence Management:** Automatically captures and stores images of detected individuals as evidence, with features for cleanup and archival.
- **Alerting System:** Notifies security personnel of watchlist matches or other critical events.
- **Robust Database System:** Uses PostgreSQL for structured data and Redis for caching and real-time messaging.

## 🏛️ System Architecture

The system is built on a microservices architecture, consisting of the following core components:

1.  **AI Engine (`services/ai-engine`):** The heart of the system, responsible for processing video streams, running face detection and recognition models, and publishing results.
2.  **Dashboard API (`services/dashboard-api`):** A FastAPI-based backend that serves the web dashboard, manages database interactions, handles user authentication, and provides WebSocket for real-time updates.
3.  **Dashboard UI (`services/dashboard-ui`):** A React and TypeScript single-page application providing the user interface for system administration and monitoring.
4.  **Databases:**
    -   **PostgreSQL:** The primary database for storing persistent data like user information, camera configurations, and evidence metadata.
    -   **Redis/Memurai:** Used for caching, session management, and as a message broker for inter-service communication.
5.  **Storage:** A dedicated `storage` directory for managing ONNX models, FAISS indexes for face recognition, and captured evidence images.

## 💻 Technology Stack

- **Backend:** Python, FastAPI, SQLAlchemy (ORM), Alembic (Migrations)
- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **AI/ML:** ONNX Runtime, OpenCV, FAISS
- **Database:** PostgreSQL, Redis
- **Deployment:** Nginx, Systemd

## 🚀 Getting Started

Follow these instructions to get a local development environment up and running.

### Prerequisites

- Python 3.9+ and `pip`
- Node.js 18+ and `npm`
- PostgreSQL Server
- Redis Server

### 1. Clone the Repository

```bash
# Since you are already in the project, you can skip this step.
# For future reference:
git clone <your-repository-url>
cd vision-ai
```

### 2. Backend Setup

First, set up and activate a Python virtual environment:

```powershell
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1
```

Install the required Python packages from the `requirements` directory:

```bash
# Install base, AI engine, and dashboard API dependencies
pip install -r requirements/base.txt
pip install -r requirements/ai-engine.txt
pip install -r requirements/dashboard-api.txt
```

### 3. Frontend Setup

Navigate to the `dashboard-ui` service directory and install the required npm packages:

```bash
cd services/dashboard-ui
npm install
cd ../..
```

### 4. Configuration

The system uses `.env` files and a central `config.yaml` for configuration.

1.  **Copy Example Environment Files:**
    ```bash
    cp config/ai-engine.env.example config/ai-engine.env
    cp config/dashboard-api.env.example config/dashboard-api.env
    ```

2.  **Update Configuration:**
    -   Open `config/config.yaml` and `config/*.env` files.
    -   Ensure the `postgres_url` and other settings match your local database setup (username, password, port). The default credentials are `postgres:admin123`.

### 5. Initialize the Database

Set up the database schema and seed the initial admin user.

```bash
# Initialize the database tables
python scripts/init_db.py

# Seed the admin user (default: Dev / Admin123)
python scripts/seed_admin.py
```

### 6. Run the System

You can run all the services using the main `start_system.py` script. This will launch the AI Engine, Dashboard API, and the Frontend dev server concurrently.

```bash
python start_system.py
```

Once the services are running, you can access the dashboard at:
**http://localhost:5173**

---
*This README was generated with assistance from GitHub Copilot.*
