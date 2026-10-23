"""Friendly names for well-known ports (5432 -> PostgreSQL)."""

COMMON_PORTS = {
    20: "FTP data", 21: "FTP", 22: "SSH", 25: "SMTP", 53: "DNS", 80: "HTTP", 110: "POP3",
    135: "Windows RPC", 139: "NetBIOS", 143: "IMAP", 443: "HTTPS", 445: "SMB", 631: "CUPS printing",
    1433: "SQL Server", 1521: "Oracle DB", 1883: "MQTT", 2049: "NFS", 2181: "ZooKeeper",
    2375: "Docker API", 2376: "Docker API (TLS)", 3000: "Node / React dev", 3001: "Node dev",
    3306: "MySQL", 3389: "Remote Desktop", 4200: "Angular dev", 4317: "OpenTelemetry",
    5000: "Flask / AirPlay", 5001: "Flask alt", 5173: "Vite dev", 5432: "PostgreSQL",
    5433: "PostgreSQL alt", 5555: "Flower", 5601: "Kibana", 5672: "RabbitMQ", 5900: "VNC",
    6379: "Redis", 6443: "Kubernetes API", 7474: "Neo4j", 8000: "Django / uvicorn",
    8080: "HTTP alt / Tomcat", 8081: "HTTP alt", 8086: "InfluxDB", 8443: "HTTPS alt",
    8501: "Streamlit", 8888: "Jupyter", 9000: "PHP-FPM / MinIO", 9090: "Prometheus",
    9092: "Kafka", 9200: "Elasticsearch", 9229: "Node debugger", 9300: "Elasticsearch nodes",
    11211: "Memcached", 15672: "RabbitMQ admin", 27017: "MongoDB",
}


def hint_for(port: int) -> str:
    """Return a short human name for a well-known port, or an empty string."""
    return COMMON_PORTS.get(port, "")
