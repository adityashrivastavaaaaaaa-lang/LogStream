# LogStream

A high-performance, scalable log ingestion and search system built with modern technologies. LogStream can handle thousands of logs per second with real-time processing and full-text search capabilities.

## 🚀 Features

- **High Performance**: Processes 901 logs per second (54,083 logs per minute)
- **Real-time Processing**: Asynchronous log ingestion via Kafka message queue
- **Full-text Search**: Fast search across all log fields and metadata
- **Scalable Architecture**: Microservices design with Docker containers
- **Web Dashboard**: User-friendly interface for log management
- **PostgreSQL Storage**: Reliable, ACID-compliant log storage
- **RESTful API**: Clean API endpoints for integration

## 🏗️ Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Frontend  │    │     API     │    │   Worker    │
│   (Nginx)   │◄──►│  (FastAPI)  │◄──►│  (Python)   │
│             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           ▼
                   ┌─────────────┐
                   │  Database   │
                   │ (PostgreSQL)│
                   └─────────────┘
                           ▲
                           │
                   ┌─────────────┐
                   │    Kafka    │
                   │  (Message   │
                   │   Queue)    │
                   └─────────────┘
```

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL
- **Message Queue**: Apache Kafka
- **Frontend**: HTML/CSS/JavaScript with Nginx
- **Containerization**: Docker & Docker Compose
- **Load Testing**: Custom Python script

## 📋 Prerequisites

- Docker and Docker Compose
- Python 3.8+ (for load testing)
- Git

## 🚀 Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/adityashrivastavaaaaaaa-lang/LogStream.git
   cd LogStream
   ```

2. **Start the system**
   ```bash
   docker-compose up --build
   ```

3. **Access the services**
   - **Web Dashboard**: http://localhost:8080
   - **API**: http://localhost:8000
   - **API Documentation**: http://localhost:8000/docs

## 📖 API Usage

### Health Check
```bash
curl http://localhost:8000/
```

### Ingest a Log
```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "level": "info",
    "service": "api",
    "message": "User login successful"
  }'
```

### Search Logs
```bash
# Get all logs (limited to 10)
curl "http://localhost:8000/search"

# Search with query
curl "http://localhost:8000/search?q=error&limit=50"
```

## 🧪 Load Testing

Test the system's performance with the included load tester:

```bash
python3 load_tester.py 10000
```

This will send 10,000 logs concurrently and measure performance metrics.

## 📁 Project Structure

```
LogStream/
├── api/                    # FastAPI service
│   ├── Dockerfile
│   └── main.py
├── worker/                 # Kafka consumer worker
│   ├── Dockerfile
│   └── worker.py
├── frontend/               # Web dashboard
│   ├── Dockerfile
│   └── index.html
├── db/                     # Database initialization
│   └── init.sql
├── docker-compose.yml      # Service orchestration
├── load_tester.py          # Performance testing script
├── TODO.md                 # Development notes
└── README.md
```

## 🔧 Configuration

All services are configured through environment variables in `docker-compose.yml`:

- **API**: Kafka and database connection settings
- **Worker**: Kafka consumer configuration
- **Database**: PostgreSQL credentials
- **Kafka**: Broker and topic settings

## 📊 Performance Benchmarks

- **Throughput**: 901 logs/second (54,083 logs/minute)
- **Latency**: Sub-second response times
- **Concurrency**: Handles 100+ concurrent connections
- **Storage**: Efficient PostgreSQL indexing for fast queries

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built with FastAPI, PostgreSQL, Kafka, and Docker
- Inspired by modern logging and observability systems
- Performance tested with custom load testing tools

---

**LogStream** - High-performance logging for the modern era 🚀
