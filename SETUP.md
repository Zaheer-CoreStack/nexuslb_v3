# NexusLB v3 - Setup & Operations Guide

## 🚀 Architecture Overview

```
┌─────────────────┐
│  Nginx LB       │  Port 80 + Basic Auth
│  (Port 80)      │  Reverse Proxy / Load Balancer
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ MediaFlow Proxy │  Port 8888
│  (MFP Engine)   │  Stream Processing & APIs
└─────────────────┘
```

## 📋 Current Files

### 1. `docker-compose.yml`
**Purpose**: Defines both services - MediaFlow Proxy and Nginx Load Balancer
- **mfp**: MediaFlow Proxy container (builds from ./mediaflow-proxy)
- **lb**: Nginx Alpine container with basic authentication

### 2. `nginx.conf`
**Purpose**: Nginx configuration with user authentication
- Listens on port 80
- Requires username/password for access (Basic Auth)
- Proxies all traffic to MediaFlow Proxy (mfp:8888)
- Health check endpoint on port 8080 (no auth required)

### 3. `.htpasswd`
**Purpose**: User credentials database for Nginx Basic Auth
- Format: `username:password_hash`
- Pre-configured users: **admin** and **demo**

---

## 🔐 User Management

### Default Credentials
| Username | Password |
|----------|----------|
| admin    | admin123 |
| demo     | demo123  |

### Add New Users

#### Option 1: Using Docker
```bash
# Add a new user interactively
docker run --rm -it httpd:alpine htpasswd -c .htpasswd newusername

# Add a new user non-interactively
docker run --rm httpd:alpine htpasswd -b .htpasswd newusername newpassword
```

#### Option 2: Locally (if you have apache2-utils)
```bash
# Install apache2-utils (Ubuntu/Debian)
sudo apt-get install apache2-utils

# Add new user to .htpasswd
htpasswd -b .htpasswd newusername newpassword

# Remove a user
htpasswd -D .htpasswd username
```

#### Option 3: Online Generator
Use an online htpasswd generator to create the hash, then add to `.htpasswd`:
```
newuser:$apr1$r31.k39T$uS70XJt.yL7R.gRO.67Z50
```

### Reload Credentials
After updating `.htpasswd`, reload Nginx without restarting:
```bash
docker-compose exec lb nginx -s reload
```

---

## 🚀 Starting Services

### Start All Services
```bash
cd /workspaces/nexuslb_v3
docker-compose up -d
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f mfp
docker-compose logs -f lb
```

### Stop Services
```bash
docker-compose down
```

### Restart Services
```bash
docker-compose restart
```

---

## 📡 Testing & Verification

### 1. Test Nginx Load Balancer (No Auth Required - Health Check)
```bash
curl -I http://localhost:8080/health
# Expected: HTTP/1.1 200 OK
```

### 2. Test Without Credentials (Should Fail)
```bash
curl -I http://localhost/
# Expected: HTTP/1.1 401 Unauthorized
```

### 3. Test With Valid Credentials (Should Succeed)
```bash
curl -u admin:admin123 -I http://localhost/
# Expected: HTTP/1.1 200 OK
```

### 4. Test MediaFlow Proxy Direct Access (No Auth Required)
```bash
curl -I http://localhost:8888/
# Expected: HTTP/1.1 200 OK
```

### 5. Test Load Balancer Proxying
```bash
# Access MediaFlow Proxy through Load Balancer
curl -u admin:admin123 http://localhost/ | head -20
# Should see MediaFlow Proxy HTML dashboard
```

---

## 🖥️ Accessing via Browser

### MediaFlow Proxy (Direct - No Auth)
```
http://localhost:8888
```

### Through Load Balancer (With Auth)
```
http://localhost
# Username: admin
# Password: admin123
```

When prompted, enter valid credentials from `.htpasswd`

---

## 📊 Upstreams & Stream Management

### MediaFlow Proxy Features
- **Multiple Upstreams**: Add multiple M3U playlists/sources
- **Stream Sharing**: Share multiple streams under one auth system
- **Caching**: Built-in stream caching and prebuffering
- **User Management**: Can create API-based users for access control

### Adding Upstreams to MediaFlow Proxy
1. Access MediaFlow Proxy dashboard: `http://localhost:8888`
2. Use the UI to add upstream sources (M3U URLs, playlists, etc.)
3. Configure extraction rules and caching preferences

---

## 🔧 Architecture Benefits

### Nginx Load Balancer Layer (Port 80)
✅ Single entry point for all users  
✅ Basic authentication for access control  
✅ Can extend with SSL/TLS, rate limiting, etc.  
✅ Lightweight and standards-based  

### MediaFlow Proxy Layer (Port 8888)
✅ Core streaming engine  
✅ Multiple upstream source support  
✅ Stream processing and caching  
✅ Exposed APIs for advanced configurations  

---

## 🚨 Troubleshooting

### Services Won't Start
```bash
# Check health
docker-compose health

# View detailed logs
docker-compose logs --no-log-prefix mfp lb

# Force restart
docker-compose down
docker-compose up -d
```

### Nginx Returns 502 (Bad Gateway)
- MediaFlow Proxy (mfp) may not be ready
- Check: `docker logs mfp`
- Wait 2-3 minutes for MFP to fully initialize

### Authentication Not Working
- Verify `.htpasswd` file exists and is readable
- Check Nginx config: `docker-compose exec lb cat /etc/nginx/nginx.conf`
- Reload config: `docker-compose exec lb nginx -s reload`

### Port Already in Use
```bash
# Find process using port 80
lsof -i :80

# Kill conflicting process
kill -9 <PID>

# Or use different port in docker-compose.yml
# Change: ports: - "8080:80"
```

---

## 📝 Configuration Customization

### Modify Nginx Ports
Edit `docker-compose.yml`:
```yaml
ports:
  - "8080:80"    # Access via http://localhost:8080
  - "8443:443"   # HTTPS when configured
```

### Add SSL/TLS
1. Add certificates to `./certs/` directory
2. Update `nginx.conf` with SSL directives
3. Reload: `docker-compose exec lb nginx -s reload`

### Rate Limiting
Add to `nginx.conf` in the http block:
```nginx
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
```

Then in the server block:
```nginx
location /api/ {
    limit_req zone=api_limit burst=20 nodelay;
    proxy_pass http://mfp_backend;
}
```

---

## 📚 Resources

- **MediaFlow Proxy Docs**: [GitHub](https://github.com/mhdzumair/mediaflow-proxy)
- **Nginx Docs**: [Official Documentation](https://nginx.org/en/docs/)
- **Docker Compose Docs**: [Official Documentation](https://docs.docker.com/compose/)

---

## ✅ Quick Checklist

- [ ] Review `docker-compose.yml` setup
- [ ] Verify `.htpasswd` users are configured
- [ ] Test Nginx health endpoint: `curl http://localhost:8080/health`
- [ ] Test with credentials: `curl -u admin:admin123 http://localhost/`
- [ ] Access MediaFlow Proxy dashboard via browser
- [ ] Add upstreams to MediaFlow Proxy
- [ ] Test streaming through load balancer
- [ ] Document any custom configurations
