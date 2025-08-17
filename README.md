# Pend Claim Analysis - Agentic Application

An AI-powered agentic application for analyzing and processing pending healthcare claims using Standard Operating Procedures (SOPs) implemented with LangGraph and Streamlit.

## Features

- **SOP-Driven Workflow**: Processes claims based on configurable Standard Operating Procedures (SOPs)
- **Agentic Processing**: Uses LangGraph to create intelligent, stateful workflows
- **Interactive UI**: Streamlit-based web interface for claim submission and monitoring
- **MCP Integration**: Connects to MCP server for SQL query execution
- **Comprehensive Logging**: Detailed logging for auditing and debugging

## Prerequisites

- Python 3.9+
- SQLite (for local development)
- Access to an MCP server (for production)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/pend-claims-agentic-workflow.git
   cd pend-claims-agentic-workflow
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. Initialize the database:
   ```bash
   python -m scripts.seed_database
   ```

## Configuration

Create a `.env` file in the project root with the following variables:

```ini
# Application
DEBUG=True
LOG_LEVEL=INFO

# Database
DATABASE_URL=sqlite:///./claims.db

# MCP Server
MCP_BASE_URL=http://localhost:8000
MCP_API_KEY=your-api-key-here

# Paths
DATA_DIR=./data
LOGS_DIR=./logs
```

## Running the Application

### Development Mode

Start the FastAPI server with hot-reload:

```bash
uvicorn app.main:app --reload
```

The Streamlit UI will be available at http://localhost:8000

### Production Mode

For production, use a production-grade ASGI server like Uvicorn with Gunicorn:

```bash
pip install gunicorn

# Start the server with 4 worker processes
gunicorn -k uvicorn.workers.UvicornWorker --workers 4 --bind 0.0.0.0:8000 app.main:app
```

## Project Structure

```
.
├── app/                          # Application source code
│   ├── config/                  # Configuration settings
│   ├── core/                    # Core application logic
│   ├── db/                      # Database models and operations
│   ├── sops/                    # Standard Operating Procedures
│   ├── ui/                      # Streamlit UI components
│   ├── workflows/               # LangGraph workflow definitions
│   └── main.py                  # FastAPI application entry point
├── data/                        # Data files
│   └── sops/                    # SOP definition files
├── scripts/                     # Utility scripts
│   └── seed_database.py         # Database seeding script
├── tests/                       # Test files
├── .env.example                 # Example environment variables
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Creating SOPs

Standard Operating Procedures (SOPs) define the workflow for processing claims. Each SOP is a JSON file in the `data/sops` directory.

### SOP File Format

```json
{
  "sop_code": "B007",
  "name": "Outpatient Physical Therapy Services",
  "description": "Process outpatient physical therapy claims",
  "version": "1.0.0",
  "condition_codes": ["B007"],
  "entry_point": "check_eligibility",
  "steps": {
    "check_eligibility": {
      "type": "query",
      "name": "Check Eligibility",
      "description": "Verify member eligibility for physical therapy",
      "query": "SELECT * FROM members WHERE member_id = :member_id",
      "params": {"member_id": "$member_id"}
    },
    "approve_claim": {
      "type": "action",
      "name": "Approve Claim",
      "description": "Approve the claim",
      "action_type": "approve_claim",
      "parameters": {
        "reason": "Claim meets all requirements"
      }
    }
  }
}
```

## API Documentation

API documentation is available at:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## Testing

Run the test suite:

```bash
pytest
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
