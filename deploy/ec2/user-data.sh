#!/bin/bash
set -euxo pipefail

REPO_URL="${REPO_URL:-https://github.com/TaegonAndreaSehoKim/DataPrep-Studio.git}"
REPO_REF="${REPO_REF:-master}"
APP_DIR="/opt/dataprep-studio"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
STORAGE_DIR="$BACKEND_DIR/app/storage"

dnf update -y
dnf install -y git nginx python3.12 python3.12-pip nodejs npm

rm -rf "$APP_DIR"
git clone "$REPO_URL" "$APP_DIR"
cd "$APP_DIR"
git checkout "$REPO_REF"

mkdir -p "$STORAGE_DIR/uploads" "$STORAGE_DIR/exports"
touch "$STORAGE_DIR/uploads/.gitkeep" "$STORAGE_DIR/exports/.gitkeep"

python3.12 -m venv "$BACKEND_DIR/.venv"
"$BACKEND_DIR/.venv/bin/python" -m pip install --upgrade pip
"$BACKEND_DIR/.venv/bin/python" -m pip install -r "$BACKEND_DIR/requirements.txt"

cat >/etc/systemd/system/dataprep-backend.service <<SERVICE
[Unit]
Description=DataPrep Studio FastAPI backend
After=network.target

[Service]
Type=simple
WorkingDirectory=$BACKEND_DIR
Environment=DATABASE_URL=sqlite:///$STORAGE_DIR/dataprep_studio.db
Environment=STORAGE_DIR=$STORAGE_DIR
Environment=UPLOAD_DIR=$STORAGE_DIR/uploads
Environment=EXPORT_DIR=$STORAGE_DIR/exports
ExecStart=$BACKEND_DIR/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

cd "$FRONTEND_DIR"
npm ci
VITE_API_BASE_URL=/api npm run build

cat >/etc/nginx/conf.d/dataprep-studio.conf <<'NGINX'
server {
    listen 80 default_server;
    server_name _;

    root /opt/dataprep-studio/frontend/dist;
    index index.html;

    client_max_body_size 25m;

    location /api/ {
        rewrite ^/api/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        try_files $uri /index.html;
    }
}
NGINX

rm -f /etc/nginx/conf.d/default.conf
systemctl daemon-reload
systemctl enable --now dataprep-backend
systemctl enable --now nginx
nginx -t
systemctl reload nginx
