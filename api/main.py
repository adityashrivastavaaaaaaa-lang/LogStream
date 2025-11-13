import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
import time

# --- Configuration ---
KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_TOPIC = os.environ.get('KAFKA_TOPIC', 'log_topic')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'logdb')
DB_USER = os.environ.get('DB_USER', 'loguser')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'logpassword')

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Global Kafka Producer ---
# We will initialize this in the lifespan event
producer: Optional[KafkaProducer] = None

# --- Pydantic Model ---
class LogIngest(BaseModel):
    level: str = Field(..., examples=["error"])
    service: str = Field(..., examples=["payment-service"])
    message: str = Field(..., examples=["Failed to process transaction 12345"])
    metadata: Optional[Dict[str, Any]] = Field(default=None, examples=[{"transaction_id": 12345, "user_id": 500}])

# --- Kafka & DB Connection Handling ---
def get_kafka_producer():
    """Tries to connect to Kafka and returns a producer instance."""
    for _ in range(5): # Retry 5 times
        try:
            _producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(','),
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all'
            )
            logger.info("Kafka producer connected successfully.")
            return _producer
        except NoBrokersAvailable:
            logger.warning("No Kafka brokers available. Retrying in 5 seconds...")
            time.sleep(5)
    logger.error("Failed to connect to Kafka producer after retries.")
    return None

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        logger.info("Database connection established.")
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Failed to connect to database: {e}")
        return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown events."""
    global producer
    logger.info("FastAPI app starting up...")
    producer = get_kafka_producer()
    
    # Check if DB is ready (worker should handle table creation, but good to check)
    db_conn = get_db_connection()
    if db_conn:
        db_conn.close()
    else:
        logger.error("Database connection failed on startup.")
        # Note: We might still run, but /search will fail.
        
    yield
    
    # --- Shutdown ---
    logger.info("FastAPI app shutting down...")
    if producer:
        producer.flush()
        producer.close()
        logger.info("Kafka producer flushed and closed.")

app = FastAPI(
    title="LogStream | Ingest & Query API",
    description="API for high-throughput log ingestion and search.",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# --- API Endpoints ---

@app.get("/", tags=["Health"])
async def read_root():
    """Root endpoint for health check."""
    return {"status": "ok", "message": "LogStream API is running."}

@app.get("/viewer", tags=["Viewer"])
async def get_viewer():
    """Serves the log viewer HTML page."""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LogStream Viewer [React]</title>
    <!-- 1. Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- 2. React Libraries -->
    <script src="https://unpkg.com/react@18/umd/react.development.js" crossorigin></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js" crossorigin></script>
    <!-- 3. Babel to transpile JSX -->
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <style>
        body { font-family: 'Inter', sans-serif; }
        .log-table-container { height: 60vh; }
        /* Simple spinner for loading state */
        .spinner {
            border: 4px solid rgba(0, 0, 0, 0.1);
            width: 24px;
            height: 24px;
            border-radius: 50%;
            border-left-color: #4f46e5; /* indigo-600 */
            animation: spin 1s ease infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body class="bg-slate-100 text-slate-800">

    <!-- This is the React root -->
    <div id="root"></div>

    <!--
      This script contains the entire React application.
      We use type="text/babel" so Babel can transpile the JSX.
    -->
    <!-- FIX: Removed data-type="module" and explicitly use window.React and window.ReactDOM -->
    <script type="text/babel">
        const { useState, useEffect, useCallback, useMemo } = window.React;
        const { createRoot } = window.ReactDOM;

        // --- Utility Components ---

        // Badge component for log levels
        const LevelBadge = ({ level }) => {
            const levelClass = useMemo(() => {
                switch (level) {
                    case 'error': return 'bg-red-100 text-red-800';
                    case 'critical': return 'bg-red-200 text-red-900 font-bold';
                    case 'warning': return 'bg-yellow-100 text-yellow-800';
                    case 'info': return 'bg-blue-100 text-blue-800';
                    case 'debug': return 'bg-green-100 text-green-800';
                    default: return 'bg-slate-100 text-slate-800';
                }
            }, [level]);

            return (
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${levelClass}`}>
                    {level}
                </span>
            );
        };

        // --- Main App Component ---
        function App() {
            // --- State ---
            const [logs, setLogs] = useState([]);
            const [totalLogs, setTotalLogs] = useState(0);
            const [loading, setLoading] = useState(false);
            const [error, setError] = useState(null);

            // --- Filter & Pagination State ---
            const [filters, setFilters] = useState({
                q: "",
                service: "",
                level: "",
                limit: 100
            });
            const [currentPage, setCurrentPage] = useState(1);
            const [autoRefresh, setAutoRefresh] = useState(false);

            // --- Derived State ---
            const totalPages = useMemo(() => Math.ceil(totalLogs / filters.limit), [totalLogs, filters.limit]);
            const offset = useMemo(() => (currentPage - 1) * filters.limit, [currentPage, filters.limit]);

            // --- Data Fetching ---
            const fetchLogs = useCallback(async (pageToFetch = currentPage) => {
                setLoading(true);
                setError(null);

                // On a new filter search, always reset to page 1
                if (pageToFetch === 'search') {
                    pageToFetch = 1;
                    setCurrentPage(1);
                }

                const params = new URLSearchParams({
                    limit: filters.limit,
                    offset: (pageToFetch - 1) * filters.limit
                });

                if (filters.q) params.append('q', filters.q);
                if (filters.service) params.append('service', filters.service);
                if (filters.level) params.append('level', filters.level);

                try {
                    // Note: We use /search directly, as it's served from the same origin
                    const response = await fetch(`/search?${params.toString()}`);
                    if (!response.ok) {
                        const errText = await response.text();
                        throw new Error(`HTTP error! Status: ${response.status} - ${errText}`);
                    }
                    const result = await response.json();
                    setLogs(result.data || []);
                    setTotalLogs(result.total_count || 0);
                } catch (err) {
                    console.error("Failed to fetch logs:", err);
                    setError(err.message);
                    setLogs([]);
                    setTotalLogs(0);
                } finally {
                    setLoading(false);
                }
            }, [filters, currentPage]); // Re-create function if filters change

            // --- Event Handlers ---
            const handleFilterChange = (e) => {
                const { name, value } = e.target;
                setFilters(prev => ({ ...prev, [name]: value }));
            };

            const handleSearch = () => {
                fetchLogs('search');
            };

            const handlePrevPage = () => {
                if (currentPage > 1) {
                    const newPage = currentPage - 1;
                    setCurrentPage(newPage);
                    fetchLogs(newPage);
                }
            };

            const handleNextPage = () => {
                if (currentPage < totalPages) {
                    const newPage = currentPage + 1;
                    setCurrentPage(newPage);
                    fetchLogs(newPage);
                }
            };

            // --- Effects ---

            // Effect for Auto-Refresh
            useEffect(() => {
                if (autoRefresh) {
                    fetchLogs(1); // Fetch immediately on check
                    const interval = setInterval(() => fetchLogs(1), 5000);
                    return () => clearInterval(interval); // Cleanup on uncheck
                }
            }, [autoRefresh]); // Only re-run when autoRefresh changes

            // --- Render ---
            return (
                <div className="container mx-auto p-4 md:p-8">
                    {/* Header */}
                    <header className="mb-6">
                        <h1 className="text-4xl font-bold text-slate-900">LogStream Viewer</h1>
                        <p className="text-lg text-slate-600">Real-time viewer for ingested logs (React Edition)</p>
                    </header>

                    {/* Filter Controls */}
                    <div className="bg-white p-4 rounded-lg shadow mb-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 items-end">
                        <div className="lg:col-span-2">
                            <label htmlFor="q-filter" className="block text-sm font-medium text-slate-700">General Search</label>
                            <input type="text" id="q-filter" name="q" value={filters.q} onChange={handleFilterChange} placeholder="e.g., 'failed' or 'user_id:1234'" className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"/>
                        </div>
                        <div>
                            <label htmlFor="service-filter" className="block text-sm font-medium text-slate-700">Service</label>
                            <input type="text" id="service-filter" name="service" value={filters.service} onChange={handleFilterChange} placeholder="e.g., payment-service" className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"/>
                        </div>
                        <div>
                            <label htmlFor="level-filter" className="block text-sm font-medium text-slate-700">Level</label>
                            <select id="level-filter" name="level" value={filters.level} onChange={handleFilterChange} className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
                                <option value="">All</option>
                                <option value="info">Info</option>
                                <option value="warning">Warning</option>
                                <option value="error">Error</option>
                                <option value="debug">Debug</option>
                                <option value="critical">Critical</option>
                            </select>
                        </div>
                        <div className="flex flex-col md:flex-row gap-4 items-end">
                             <button
                                id="search-btn"
                                onClick={handleSearch}
                                disabled={loading}
                                className="w-full bg-indigo-600 text-white px-5 py-2 rounded-md shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50 flex items-center justify-center"
                            >
                                {loading ? <div className="spinner" /> : <span>Search</span>}
                            </button>
                        </div>
                    </div>

                    {/* Auto-Refresh & Status */}
                    <div className="flex justify-between items-center mb-6 px-1">
                        <div className="flex items-center">
                            <input type="checkbox" id="auto-refresh" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
                            <label htmlFor="auto-refresh" className="ml-2 block text-sm text-slate-900">Auto-refresh (5s)</label>
                        </div>
                        <div id="status-indicator" className="p-2 text-sm text-slate-500">
                            {loading ? "Loading..." : (error ? "Error" : "Idle")}
                        </div>
                    </div>

                    {/* Pagination Controls */}
                    <div className="flex justify-between items-center mb-6 px-1">
                        <span id="page-info" className="text-sm text-slate-700">
                            {totalLogs > 0
                                ? `Showing ${offset + 1} - ${Math.min(offset + filters.limit, totalLogs)} of ${totalLogs} logs`
                                : "No results found."
                            }
                        </span>
                        <div className="flex gap-2">
                            <button id="prev-btn" onClick={handlePrevPage} disabled={currentPage === 1 || loading} className="bg-white text-slate-700 px-4 py-2 rounded-md shadow-sm border border-slate-300 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1">
                                < Previous
                            </button>
                            <button id="next-btn" onClick={handleNextPage} disabled={currentPage >= totalPages || loading} className="bg-white text-slate-700 px-4 py-2 rounded-md shadow-sm border border-slate-300 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1">
                                Next >
                            </button>
                        </div>
                    </div>

                    {/* Log Table Area */}
                    <div className="bg-white shadow-lg rounded-lg overflow-hidden">
                        <div className="overflow-x-auto">
                            <div className="log-table-container overflow-y-auto">
                                <table className="min-w-full divide-y divide-slate-200">
                                    <thead className="bg-slate-50 sticky top-0">
                                        <tr>
                                            <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Timestamp</th>
                                            <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Level</th>
                                            <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Service</th>
                                            <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Message</th>
                                            <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Metadata</th>
                                        </tr>
                                    </thead>
                                    <tbody id="log-table-body" className="bg-white divide-y divide-slate-200">
                                        {loading && (
                                            <tr>
                                                <td colSpan="5" className="p-8 text-center text-slate-500">
                                                    <div className="spinner mx-auto" />
                                                </td>
                                            </tr>
                                        )}
                                        {error && (
                                            <tr>
                                                <td colSpan="5" className="p-8 text-center text-red-600">
                                                    {/* FIX: Corrected typo name.="ServerCrash" to name="ServerCrash" and removed Icon component */}
                                                    <span className="text-2xl">⚠️</span>
                                                    <p className="font-medium">Failed to load logs.</p>
                                                    <span className="text-sm text-slate-500">{error}</span>
                                                </td>
                                            </tr>
                                        )}
                                        {!loading && !error && logs.length === 0 && (
                                             <tr>
                                                <td colSpan="5" className="p-8 text-center text-slate-500">
                                                    <span className="text-2xl">🔍</span>
                                                    <p>No logs found.</p>
                                                    <span className="text-sm">Try adjusting your search filters.</span>
                                                </td>
                                            </tr>
                                        )}
                                        {!loading && !error && logs.length > 0 && logs.map(log => (
                                            <tr key={log.id} className="hover:bg-slate-50">
                                                <td className="px-4 py-3 whitespace-nowrap text-sm text-slate-600">{new Date(log.timestamp).toLocaleString()}</td>
                                                <td className="px-4 py-3 whitespace-nowrap text-sm">
                                                    <LevelBadge level={log.level} />
                                                </td>
                                                <td className="px-4 py-3 whitespace-nowMrap text-sm font-medium text-slate-800">{log.service}</td>
                                                <td className="px-4 py-3 text-sm text-slate-600 truncate" style={{maxWidth: "300px"}} title={log.message}>{log.message}</td>
                                                <td className="px-4 py-3 text-sm text-slate-500">
                                                    <pre className="text-xs bg-slate-50 p-2 rounded overflow-auto" style={{maxHeight: '100px'}}>
                                                        {JSON.stringify(log.metadata, null, 2)}
                                                    </pre>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }

        // --- Mount the App ---
        // Ensure this runs only after all scripts are loaded
        document.addEventListener("DOMContentLoaded", () => {
             // Check if React and ReactDOM are loaded
            if (typeof window.React === 'undefined' || typeof window.ReactDOM === 'undefined') {
                console.error("React or ReactDOM did not load.");
                document.getElementById('root').innerHTML = '<div style="padding: 20px; text-align: center; color: red;">Error: React libraries failed to load.</div>';
                return;
            }

            const root = window.ReactDOM.createRoot(document.getElementById('root'));
            root.render(window.React.createElement(App));
        });

    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content, status_code=200)

@app.post("/ingest", status_code=status.HTTP_202_ACCEPTED, tags=["Ingestion"])
async def ingest_log(log: LogIngest):
    """
    Asynchronously ingests a log entry.
    
    The log is sent to a Kafka topic for background processing.
    """
    global producer
    if not producer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kafka producer is not available."
        )

    # Add a server-side timestamp for consistency
    log_data = log.model_dump()
    log_data['timestamp'] = datetime.utcnow().isoformat()

    try:
        # Send log to Kafka
        producer.send(KAFKA_TOPIC, value=log_data)
        
        # We can flush immediately for lower latency, or batch for higher throughput
        # producer.flush() 
        
        return {"status": "accepted", "message": "Log queued for processing."}
    except Exception as e:
        logger.error(f"Failed to send log to Kafka: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue log: {str(e)}"
        )

@app.get("/search", tags=["Querying"])
async def search_logs(
    q: Optional[str] = Query(None, description="General search query: full-text on message or key:value on metadata"),
    level: Optional[str] = Query(None, description="Filter by log level (e.g., 'error')"),
    service: Optional[str] = Query(None, description="Filter by service name (e.g., 'payment-service')"),
    timestamp_start: Optional[datetime] = Query(None, description="ISO 8601 start timestamp"),
    timestamp_end: Optional[datetime] = Query(None, description="ISO 8601 end timestamp"),
    limit: int = Query(100, ge=1, le=1000, description="Number of logs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    Queries logs from the PostgreSQL database with filters.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection is not available."
            )
            
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = "SELECT * FROM logs WHERE 1=1"
            params = []

            if q:
                if ':' in q:
                    # Key:value search on metadata
                    key, value = q.split(':', 1)
                    query += " AND metadata ->> %s = %s"
                    params.extend([key, value])
                else:
                    # Full-text search on message (case-insensitive)
                    query += " AND LOWER(message) LIKE LOWER(%s)"
                    params.append(f"%{q}%")

            if level:
                query += " AND level = %s"
                params.append(level)
            if service:
                query += " AND service = %s"
                params.append(service)
            if timestamp_start:
                query += " AND timestamp >= %s"
                params.append(timestamp_start)
            if timestamp_end:
                query += " AND timestamp <= %s"
                params.append(timestamp_end)

            query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])

            cursor.execute(query, tuple(params))
            logs = cursor.fetchall()

            # Get total count for pagination
            count_query = query.replace("SELECT * FROM logs", "SELECT COUNT(*) as count FROM logs").replace(" ORDER BY timestamp DESC LIMIT %s OFFSET %s", "")
            count_params = params[:-2]  # Remove limit and offset
            cursor.execute(count_query, tuple(count_params))
            total_result = cursor.fetchone()
            total = total_result['count'] if total_result else 0

            return {"status": "success", "total": total, "data": logs}

    except psycopg2.Error as e:
        logger.error(f"Database query error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    finally:
        if conn:
            conn.close()
