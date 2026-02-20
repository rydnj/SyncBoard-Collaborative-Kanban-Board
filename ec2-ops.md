# EC2 & Elastic IP Operations Guide

## Your Setup
- **Instance:** t2.micro (AWS free tier)
- **OS:** Ubuntu 24.04 LTS
- **Elastic IP:** YOUR_ELASTIC_IP (static — won't change on restart)
- **Ports open:** 22 (SSH), 3000 (frontend), 8000 (backend)
- **Free tier:** 750 hrs/month of t2.micro for 12 months from account creation

---

## Daily Operations

### SSH into the instance
```bash
ssh -i ~/.ssh/syncboard-key.pem ubuntu@YOUR_ELASTIC_IP
```

### Check if everything is running
```bash
docker-compose ps
```
All three containers (db, backend, frontend) should show as `Up`.

### View logs
```bash
# All containers
docker-compose logs -f

# Specific container
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Deploy a code update
```bash
cd ~/SyncBoard-Collaborative-Kanban-Board
git pull
docker-compose up --build -d  # rebuild changed services
```

### Restart a single service (no rebuild)
```bash
docker-compose restart backend
docker-compose restart frontend
```

---

## Stopping the Instance

### When to stop
- You're done actively demoing/job searching
- You want to conserve free tier hours
- You're not using it for more than a few days

### How to stop (AWS Console)
1. AWS Console → EC2 → Instances
2. Select your syncboard instance
3. Instance State → **Stop**

### ⚠️ Elastic IP warning
Elastic IPs are **free while attached to a running instance** but cost ~$0.005/hr when the instance is stopped. Over a month that's ~$3.60 — small but avoidable.

**Option A — Keep the Elastic IP (recommended if stopping temporarily)**
Just stop the instance. The IP stays reserved. When you restart, the same IP works immediately. Cost: ~$0.005/hr while stopped.

**Option B — Release the Elastic IP (if stopping for a long time)**
1. EC2 → Elastic IPs
2. Select your IP → Actions → **Disassociate**
3. Then Actions → **Release**

When you want to redeploy later, allocate a new Elastic IP, associate it, update `.env` on EC2, and rebuild the frontend.

---

## Restarting the Instance

### Start from AWS Console
1. EC2 → Instances → select instance
2. Instance State → **Start**
3. Wait ~60 seconds for it to fully boot

### Reconnect and verify
```bash
ssh -i ~/.ssh/syncboard-key.pem ubuntu@YOUR_ELASTIC_IP

# Check Docker is running
sudo systemctl status docker

# Start containers if they're not running
cd ~/SyncBoard-Collaborative-Kanban-Board
docker-compose up -d
```

### Why containers might not auto-start
Docker itself starts automatically on boot (`systemctl enable docker`), but `docker-compose up` is not set to run on boot. If you restart the instance, SSH in and run `docker-compose up -d` manually. This is intentional — auto-starting on boot can cause issues if the DB isn't ready yet.

---

## Terminating the Instance (Permanent)

Only do this when you're completely done with the project.

### Before terminating
- [ ] Make sure all code is pushed to GitHub
- [ ] Download any data you need from the DB (optional — this is a portfolio project so likely not needed)
- [ ] Disassociate and release the Elastic IP first (otherwise it keeps billing)

### How to terminate
1. EC2 → Elastic IPs → Disassociate → Release
2. EC2 → Instances → select instance → Instance State → **Terminate**

⚠️ Termination is permanent. The disk and all data are deleted. There is no undo.

---

## Cost Summary

| Resource | Cost |
|----------|------|
| t2.micro running (free tier) | $0/hr for first 12 months |
| t2.micro running (after free tier) | ~$0.012/hr (~$8.76/month) |
| Elastic IP (instance running) | $0 |
| Elastic IP (instance stopped) | ~$0.005/hr (~$3.60/month) |
| Data transfer (portfolio usage) | Negligible |

**Set a billing alert** so you're never surprised:
1. AWS Console → Billing → Budgets → Create Budget
2. Set a $5 monthly alert — you'll get an email before any meaningful charges

---

## Useful Commands Cheatsheet

```bash
# SSH in
ssh -i ~/.ssh/syncboard-key.pem ubuntu@YOUR_ELASTIC_IP

# Check container status
docker-compose ps

# Start all containers
docker-compose up -d

# Stop all containers (keeps data)
docker-compose down

# Rebuild and restart
docker-compose up --build -d

# View live logs
docker-compose logs -f

# Run DB migrations (after fresh deploy)
docker-compose exec backend alembic upgrade head

# Free up disk space (careful — deletes unused images)
docker system prune -a
```
