# Docker Deployment Package

## What's Working
✅ **Local Docker deployment tested and working**
- React app builds and runs in production mode with nginx
- Accessible at `http://localhost` 
- Uses standard port 80 for web traffic

## Files to Deploy

### Core Application Files (already in repo)
```
sr-front-end/
├── src/                  # React frontend source
├── public/              # React public assets  
├── backend.js           # Node.js backend (currently down, being rebuilt)
├── package.json         # Dependencies and scripts
├── package-lock.json    # Locked dependency versions
```

### Docker Configuration Files (add these 3)
```
├── Dockerfile           # Multi-stage production build with nginx
├── docker-compose.yml   # Container orchestration 
├── .dockerignore        # Build optimization
```

## Deployment Instructions

### For AWS EC2 Deployment
1. **Launch EC2 instance** (t3.micro or larger, Amazon Linux 2)
2. **Security Groups**: Allow HTTP (80) and SSH (22) 
3. **Install Docker and Docker Compose** on the instance
4. **Clone the repository**
5. **Run**: `docker-compose up -d --build`

### The app will be accessible at: `http://EC2_PUBLIC_IP`

## Docker Commands Reference
```bash
# Deploy
docker-compose up -d --build

# Check status
docker-compose ps

# View logs
docker-compose logs

# Update deployment
git pull
docker-compose up -d --build

# Stop
docker-compose down
```

## Technical Notes

- **Port**: Application runs on standard port 80
- **Architecture**: Multi-stage Docker build (Node.js build → nginx serve)
- **Frontend Only**: Backend is currently being rebuilt
- **SPARQL**: App makes client-side requests to SPARQL endpoints (CORS-enabled)
- **Production Ready**: Optimized React build with nginx web server

## Alternative Deployment Options

Your colleague might prefer:
- **AWS ECS** (Elastic Container Service) for better scalability
- **AWS App Runner** for simpler container deployment
- **AWS Amplify** if it's purely frontend
- **Application Load Balancer** + multiple EC2 instances for high availability

## Future: Adding Backend

When the backend is rebuilt:
- Add backend service to `docker-compose.yml`
- Backend will likely run on port 5000 or similar
- Frontend can communicate with backend via Docker networking

---

**Status**: Frontend containerization complete and tested ✅  
**Next**: AWS deployment by your colleague  
**Later**: Add backend service when ready