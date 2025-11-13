import os
import json
import logging
import time
import sys

import psycopg2
from psycopg2.extras import Json
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

# --- Configuration ---
KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_TOPIC = os.environ.get('KAFKA_TOPIC', 'log_topic')
KAFKA_GROUP_ID = os.environ.get('KAFKA_GROUP_ID', 'log_consumer_group')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'logdb')
DB_USER = os.environ.get('DB_USER', 'loguser')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'logpassword')

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Establishes a persistent connection to the PostgreSQL database."""
    logger.info("Attempting to connect to database...")
    while True:
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            logger.info("Database connection established successfully.")
            return conn
        except psycopg2.OperationalError as e:
            logger.warning(f"Database connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

def get_kafka_consumer():
    """Establishes a connection to the Kafka cluster."""
    logger.info("Attempting to connect to Kafka consumer...")
    while True:
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(','),
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                group_id=KAFKA_GROUP_ID,
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            logger.info("Kafka consumer connected successfully.")
            return consumer
        except NoBrokersAvailable:
            logger.warning("No Kafka brokers available. Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            logger.error(f"An unexpected error occurred connecting to Kafka: {e}")
            time.sleep(5)

def main():
    """Main worker loop: Consume from Kafka and insert into PostgreSQL."""
    consumer = get_kafka_consumer()
    db_conn = get_db_connection()
    db_conn.autocommit = True # Autocommit for simpler inserts

    logger.info("Worker is running and listening for messages...")

    try:
        with db_conn.cursor() as cursor:
            for message in consumer:
                log_data = message.value

                # Basic validation
                if not isinstance(log_data, dict):
                    logger.warning(f"Skipping invalid message (not a dict): {log_data}")
                    continue

                try:
                    # Prepare data for insertion
                    timestamp = log_data.get('timestamp')
                    level = log_data.get('level')
                    service = log_data.get('service')
                    log_message = log_data.get('message')
                    # Use psycopg2.extras.Json to handle None or dict
                    metadata = Json(log_data.get('metadata'))

                    insert_query = """
                    INSERT INTO logs (timestamp, level, service, message, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    """

                    cursor.execute(insert_query, (timestamp, level, service, log_message, metadata))
                    logger.info(f"Inserted log from service: {service}")

                except psycopg2.Error as e:
                    logger.error(f"Failed to insert log into DB: {e}")
                    # In a real app, you might want to retry or send to a dead-letter queue
                    # For now, we just log and continue
                except Exception as e:
                    logger.error(f"Error processing message: {log_data}, Error: {e}")

    except KeyboardInterrupt:
        logger.info("Worker shutting down...")
    except Exception as e:
        logger.error(f"Critical error in worker loop: {e}")
    finally:
        consumer.close()
        db_conn.close()
        logger.info("Worker has shut down.")

if __name__ == "__main__":
    main()
