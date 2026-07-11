# AWS EC2 Demo Deployment

This deployment is intended for a portfolio/demo instance, not a production multi-user service.

## Shape

```text
EC2
├─ Nginx on port 80
├─ React static build under /opt/dataprep-studio/frontend/dist
├─ /api reverse proxy to FastAPI on 127.0.0.1:8000
├─ SQLite database on the EC2 EBS volume
└─ local uploads/exports under backend/app/storage
```

## Why This Shape

The current MVP is local-first and file-system backed. A single EC2 host preserves that architecture while making the app reachable as an online demo.

For a production service, move persistence to RDS and file artifacts to S3 before accepting real users.

## Bootstrap Script

The EC2 user-data script is:

```text
deploy/ec2/user-data.sh
```

It installs system packages, clones the repository, creates a backend virtual environment, installs backend dependencies, builds the frontend with `VITE_API_BASE_URL=/api`, configures Nginx, and starts a `dataprep-backend` systemd service.

## Manual Checks

On the instance:

```bash
systemctl status dataprep-backend
systemctl status nginx
curl http://127.0.0.1:8000/health
curl http://127.0.0.1/api/health
```

From a browser:

```text
http://<ec2-public-dns>
```

## Demo Caveats

- No authentication is enabled.
- Uploaded CSVs and generated exports live on the EC2 EBS volume.
- Anyone with the URL can create projects and upload CSV files.
- Keep upload size limits in place.
- Stop or terminate the instance when the demo is not needed.
