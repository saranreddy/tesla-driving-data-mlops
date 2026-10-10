#!/bin/bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a /var/log/teslamate-setup.log
}

log "Starting TeslaMate setup..."

log "Installing system dependencies..."
# DPkg::Lock::Timeout=600 prevents failures when unattended-upgrades holds the lock
apt-get -o DPkg::Lock::Timeout=600 update
apt-get -o DPkg::Lock::Timeout=600 install -y \
  docker.io \
  docker-compose-v2 \
  curl \
  python3-pip \
  python3-venv \
  postgresql-client \
  unzip
# Note: Ubuntu 24.04 has no `awscli` apt package; AWS CLI v2 is installed separately below.
# Note: `curl` is required for the AWS CLI v2 installer.

systemctl enable docker
systemctl start docker

usermod -aG docker ubuntu

log "Installing AWS CLI v2..."
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o "/tmp/awscliv2.zip"
unzip -q /tmp/awscliv2.zip -d /tmp
/tmp/aws/install
rm -rf /tmp/aws /tmp/awscliv2.zip

log "Creating 2 GB swap file (1 GB RAM instances)..."
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
swapon --show

log "Fetching secrets from SSM Parameter Store..."
ENCRYPTION_KEY=$(aws ssm get-parameter --name "${encryption_key}" --with-decryption --query 'Parameter.Value' --output text --region "${aws_region}")
POSTGRES_PASSWORD=$(aws ssm get-parameter --name "${postgres_pass}" --with-decryption --query 'Parameter.Value' --output text --region "${aws_region}")
GRAFANA_ADMIN_PASSWORD=$(aws ssm get-parameter --name "${grafana_pass}" --with-decryption --query 'Parameter.Value' --output text --region "${aws_region}")

log "Creating TeslaMate directory and Docker Compose configuration..."
mkdir -p /opt/teslamate

cat > /opt/teslamate/docker-compose.yml <<'COMPOSE_EOF'
services:
  teslamate:
    image: teslamate/teslamate:latest
    restart: always
    environment:
      - ENCRYPTION_KEY=$${TESLAMATE_ENCRYPTION_KEY}
      - DATABASE_USER=teslamate
      - DATABASE_PASS=$${POSTGRES_PASSWORD}
      - DATABASE_NAME=teslamate
      - DATABASE_HOST=database
      - MQTT_HOST=mosquitto
      - TZ=UTC
    ports:
      - 4000:4000
    cap_drop:
      - all
    mem_limit: 256m
    mem_reservation: 128m
    depends_on:
      - database
      - mosquitto

  database:
    image: postgres:17
    restart: always
    command: >
      postgres
      -c shared_buffers=128MB
      -c work_mem=4MB
      -c maintenance_work_mem=64MB
      -c effective_cache_size=256MB
      -c max_connections=20
    environment:
      - POSTGRES_USER=teslamate
      - POSTGRES_PASSWORD=$${POSTGRES_PASSWORD}
      - POSTGRES_DB=teslamate
    ports:
      - 127.0.0.1:5432:5432
    mem_limit: 384m
    mem_reservation: 256m
    volumes:
      - teslamate-db:/var/lib/postgresql/data

  grafana:
    image: teslamate/grafana:latest
    restart: always
    environment:
      - DATABASE_USER=teslamate
      - DATABASE_PASS=$${POSTGRES_PASSWORD}
      - DATABASE_NAME=teslamate
      - DATABASE_HOST=database
      - GF_SECURITY_ADMIN_PASSWORD=$${GRAFANA_ADMIN_PASSWORD}
      - GF_SERVER_ROOT_URL=http://localhost:3000
      - GF_DATABASE_CACHE_MODE=shared
      - GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH=/var/lib/grafana/dashboards/overview.json
    mem_limit: 256m
    mem_reservation: 128m
    ports:
      - 3000:3000
    volumes:
      - teslamate-grafana-data:/var/lib/grafana

  mosquitto:
    image: eclipse-mosquitto:2
    restart: always
    command: mosquitto -c /mosquitto-no-auth.conf
    mem_limit: 64m
    mem_reservation: 32m
    volumes:
      - mosquitto-conf:/mosquitto/config
      - mosquitto-data:/mosquitto/data

volumes:
  teslamate-db:
  teslamate-grafana-data:
  mosquitto-conf:
  mosquitto-data:
COMPOSE_EOF

log "Creating environment file with secrets..."
cat > /opt/teslamate/.env <<ENV_EOF
TESLAMATE_ENCRYPTION_KEY='$ENCRYPTION_KEY'
POSTGRES_PASSWORD='$POSTGRES_PASSWORD'
GRAFANA_ADMIN_PASSWORD='$GRAFANA_ADMIN_PASSWORD'
ENV_EOF

chmod 600 /opt/teslamate/.env

log "Starting TeslaMate services..."
cd /opt/teslamate
docker compose up -d

log "Installing Python dependencies for export script..."
python3 -m venv /opt/teslamate/venv
/opt/teslamate/venv/bin/pip install --upgrade pip
/opt/teslamate/venv/bin/pip install psycopg2-binary pandas pyarrow boto3 s3fs

log "Creating export script..."
cat > /opt/teslamate/export_parquet.py <<'EXPORT_SCRIPT'
#!/usr/bin/env python3
"""Export TeslaMate data to Parquet format in S3.

Exports drives and charges from the TeslaMate PostgreSQL database to Parquet files
in S3, partitioned by date. Idempotent: safe to run multiple times for the same date.
"""
import argparse
import logging
import os
import sys
from datetime import datetime, timedelta

import boto3
import pandas as pd
import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def get_db_connection(host="localhost", port=5432, user="teslamate", password=None, dbname="teslamate"):
    """Connect to TeslaMate PostgreSQL database."""
    return psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname,
    )


def export_drives(conn, date_str, s3_bucket, s3_prefix="raw/drives"):
    """Export drives for a given date to S3 Parquet."""
    query = """
    SELECT
        d.id,
        d.start_date,
        d.end_date,
        sa.display_name as start_address,
        ea.display_name as end_address,
        d.distance,
        EXTRACT(EPOCH FROM (d.end_date - d.start_date)) / 60 as duration_min,
        d.start_km,
        d.end_km,
        d.start_rated_range_km - d.end_rated_range_km as kwh_used,
        d.start_ideal_battery_range_km as start_battery_level,
        d.end_ideal_battery_range_km as end_battery_level,
        d.outside_temp_avg,
        d.speed_max,
        CASE 
            WHEN d.distance > 0 THEN ((d.start_rated_range_km - d.end_rated_range_km) / d.distance) * 1000
            ELSE NULL
        END as efficiency
    FROM drives d
    LEFT JOIN addresses sa ON d.start_address_id = sa.id
    LEFT JOIN addresses ea ON d.end_address_id = ea.id
    WHERE DATE(d.start_date) = %s
    ORDER BY d.start_date
    """
    
    df = pd.read_sql_query(query, conn, params=(date_str,))
    
    if df.empty:
        logger.info(f"No drives found for {date_str}")
        return 0
    
    s3_key = f"{s3_prefix}/date={date_str}/drives.parquet"
    
    df.to_parquet(
        f"s3://{s3_bucket}/{s3_key}",
        engine="pyarrow",
        compression="snappy",
        index=False,
    )
    
    logger.info(f"Exported {len(df)} drives to s3://{s3_bucket}/{s3_key}")
    return len(df)


def export_charges(conn, date_str, s3_bucket, s3_prefix="raw/charges"):
    """Export charges for a given date to S3 Parquet."""
    query = """
    SELECT
        c.id,
        c.start_date,
        c.end_date,
        a.display_name as address,
        c.charge_energy_added,
        c.start_ideal_battery_range_km as start_battery_level,
        c.end_ideal_battery_range_km as end_battery_level,
        EXTRACT(EPOCH FROM (c.end_date - c.start_date)) / 60 as duration_min,
        c.cost
    FROM charging_processes c
    LEFT JOIN addresses a ON c.address_id = a.id
    WHERE DATE(c.start_date) = %s
    ORDER BY c.start_date
    """
    
    df = pd.read_sql_query(query, conn, params=(date_str,))
    
    if df.empty:
        logger.info(f"No charges found for {date_str}")
        return 0
    
    s3_key = f"{s3_prefix}/date={date_str}/charges.parquet"
    
    df.to_parquet(
        f"s3://{s3_bucket}/{s3_key}",
        engine="pyarrow",
        compression="snappy",
        index=False,
    )
    
    logger.info(f"Exported {len(df)} charges to s3://{s3_bucket}/{s3_key}")
    return len(df)


def main():
    parser = argparse.ArgumentParser(description="Export TeslaMate data to Parquet in S3")
    parser.add_argument("--date", help="Date to export (YYYY-MM-DD), defaults to yesterday")
    parser.add_argument("--db-host", default="localhost", help="PostgreSQL host")
    parser.add_argument("--db-port", type=int, default=5432, help="PostgreSQL port")
    parser.add_argument("--db-user", default="teslamate", help="PostgreSQL user")
    parser.add_argument("--db-password", help="PostgreSQL password (or set POSTGRES_PASSWORD env var)")
    parser.add_argument("--db-name", default="teslamate", help="PostgreSQL database name")
    parser.add_argument("--s3-bucket", required=True, help="S3 bucket for exports")
    
    args = parser.parse_args()
    
    if args.date:
        date_str = args.date
    else:
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")
    
    db_password = args.db_password or os.environ.get("POSTGRES_PASSWORD")
    if not db_password:
        logger.error("Database password required (--db-password or POSTGRES_PASSWORD env var)")
        sys.exit(1)
    
    try:
        logger.info(f"Connecting to database at {args.db_host}:{args.db_port}")
        conn = get_db_connection(
            host=args.db_host,
            port=args.db_port,
            user=args.db_user,
            password=db_password,
            dbname=args.db_name,
        )
        
        logger.info(f"Exporting data for {date_str} to s3://{args.s3_bucket}")
        
        drives_count = export_drives(conn, date_str, args.s3_bucket)
        charges_count = export_charges(conn, date_str, args.s3_bucket)
        
        logger.info(f"Export complete: {drives_count} drives, {charges_count} charges")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Export failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
EXPORT_SCRIPT

chmod +x /opt/teslamate/export_parquet.py

log "Creating systemd timer for nightly exports..."
cat > /etc/systemd/system/teslamate-export.service <<SERVICE_EOF
[Unit]
Description=Export TeslaMate data to S3 Parquet
After=docker.service

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/teslamate
Environment="POSTGRES_PASSWORD=$POSTGRES_PASSWORD"
ExecStart=/opt/teslamate/venv/bin/python /opt/teslamate/export_parquet.py \\
  --db-host localhost \\
  --db-password $POSTGRES_PASSWORD \\
  --s3-bucket ${s3_bucket}
StandardOutput=journal
StandardError=journal
SERVICE_EOF

cat > /etc/systemd/system/teslamate-export.timer <<TIMER_EOF
[Unit]
Description=Nightly TeslaMate data export timer

[Timer]
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
TIMER_EOF

systemctl daemon-reload
systemctl enable teslamate-export.timer
systemctl start teslamate-export.timer

log "Creating daily database backup script..."
cat > /opt/teslamate/backup_db.sh <<'BACKUP_SCRIPT'
#!/bin/bash
set -euo pipefail

BACKUP_DATE=$(date +'%Y-%m-%d')
BACKUP_FILE="/tmp/teslamate_backup_$BACKUP_DATE.sql.gz"

echo "[$(date)] Starting database backup..."

source /opt/teslamate/.env

docker exec teslamate-database-1 pg_dump -U teslamate teslamate | gzip > "$BACKUP_FILE"

aws s3 cp "$BACKUP_FILE" "s3://${s3_bucket}/backups/teslamate_$BACKUP_DATE.sql.gz" --region "${aws_region}"

rm -f "$BACKUP_FILE"

echo "[$(date)] Backup complete: s3://${s3_bucket}/backups/teslamate_$BACKUP_DATE.sql.gz"
BACKUP_SCRIPT

chmod +x /opt/teslamate/backup_db.sh

cat > /etc/systemd/system/teslamate-backup.service <<BACKUP_SERVICE_EOF
[Unit]
Description=Backup TeslaMate database to S3
After=docker.service

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/teslamate
ExecStart=/opt/teslamate/backup_db.sh
StandardOutput=journal
StandardError=journal
BACKUP_SERVICE_EOF

cat > /etc/systemd/system/teslamate-backup.timer <<BACKUP_TIMER_EOF
[Unit]
Description=Daily TeslaMate database backup timer

[Timer]
OnCalendar=01:00
Persistent=true

[Install]
WantedBy=timers.target
BACKUP_TIMER_EOF

systemctl daemon-reload
systemctl enable teslamate-backup.timer
systemctl start teslamate-backup.timer

log "Setup complete! TeslaMate is running."
log "Use AWS Systems Manager Session Manager to access the instance."
log "Export timer: systemctl status teslamate-export.timer"
log "Backup timer: systemctl status teslamate-backup.timer"
