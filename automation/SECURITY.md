# Security Guidelines for Trading Automation Stack

## 🚨 CRITICAL SECURITY WARNINGS

**This system handles real money and financial data. Security is paramount.**

### Immediate Actions Required

1. **Change all default passwords** in `.env` file
2. **Use strong, unique API keys** for all services
3. **Enable 2FA** on Capital.com account
4. **Restrict network access** to n8n and database
5. **Monitor all system events** for suspicious activity

## 🔐 Authentication & Authorization

### API Keys & Secrets

**Capital.com API Credentials:**
- Store in `.env` file (never commit to git)
- Use demo credentials for testing
- Rotate keys every 90 days
- Enable IP whitelisting on Capital.com account

**Approval Secret:**
```bash
# Generate strong secret (32+ characters)
openssl rand -hex 32
# Add to .env: APPROVAL_SECRET=<generated_secret>
```

**Database Credentials:**
- Use strong passwords (16+ characters)
- Different passwords for each environment
- Regular rotation schedule

### n8n Security

**Basic Authentication:**
```bash
# In .env file
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=<strong_password>
```

**Network Security:**
- Bind n8n to localhost only: `N8N_HOST=127.0.0.1`
- Use reverse proxy (nginx) for HTTPS
- Enable firewall rules
- Consider VPN access only

## 🛡️ Network Security

### Firewall Configuration

**Block unnecessary ports:**
```bash
# Allow only required ports
ufw allow 22    # SSH
ufw allow 80      # HTTP (if using reverse proxy)
ufw allow 443    # HTTPS
ufw allow 5678   # n8n (restrict to specific IPs)
ufw deny 5432    # PostgreSQL (internal only)
```

**Restrict n8n access:**
```bash
# Allow n8n only from specific IPs
ufw allow from 192.168.1.0/24 to any port 5678
ufw deny 5678
```

### Docker Security

**Run containers as non-root:**
```yaml
# In docker-compose.yml
services:
  n8n:
    user: "1000:1000"
  mcp-caller:
    user: "1000:1000"
```

**Limit container capabilities:**
```yaml
services:
  mcp-caller:
    cap_drop:
      - ALL
    cap_add:
      - NET_ADMIN
```

## 🔒 Data Protection

### Database Security

**Encrypt sensitive data:**
```sql
-- Encrypt approval tokens
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Store encrypted tokens
INSERT INTO approvals (token_encrypted) 
VALUES (pgp_sym_encrypt('token', 'encryption_key'));
```

**Access control:**
```sql
-- Create read-only user for monitoring
CREATE USER monitor WITH PASSWORD 'monitor_password';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO monitor;
```

**Backup encryption:**
```bash
# Encrypt database backups
docker-compose exec db pg_dump -U trader trading | \
  gpg --symmetric --cipher-algo AES256 --output backup_$(date +%Y%m%d).sql.gpg
```

### Environment Variables

**Never commit secrets:**
```bash
# .gitignore
.env
.env.local
.env.production
secrets/
*.key
*.pem
```

**Use secret management:**
```bash
# For production, use Docker secrets
echo "your_secret" | docker secret create approval_secret -
```

## 🚨 Monitoring & Alerting

### Security Event Monitoring

**Monitor failed authentications:**
```sql
SELECT * FROM system_events 
WHERE event_type = 'AUTH_FAILURE' 
AND occurred_at > NOW() - INTERVAL '1 hour';
```

**Track approval token usage:**
```sql
SELECT approver, COUNT(*) as approvals
FROM approvals 
WHERE approved_at > NOW() - INTERVAL '24 hours'
GROUP BY approver;
```

**Monitor unusual trading activity:**
```sql
SELECT * FROM intents 
WHERE created_at > NOW() - INTERVAL '1 hour'
AND qty > (SELECT AVG(qty) * 2 FROM intents WHERE created_at > NOW() - INTERVAL '24 hours');
```

### Alert Configuration

**Set up alerts for:**
- Multiple failed login attempts
- Unusual trading volumes
- API key usage from new IPs
- Database connection failures
- MCP server errors

**Example alert script:**
```bash
#!/bin/bash
# security_monitor.sh

# Check for failed authentications
FAILED_AUTH=$(docker-compose exec -T db psql -U trader -d trading -t -c \
  "SELECT COUNT(*) FROM system_events WHERE event_type = 'AUTH_FAILURE' AND occurred_at > NOW() - INTERVAL '1 hour';")

if [ "$FAILED_AUTH" -gt 5 ]; then
  echo "ALERT: $FAILED_AUTH failed authentications in last hour" | \
    mail -s "Security Alert" admin@yourdomain.com
fi
```

## 🔍 Audit Trail

### Logging Requirements

**All trading actions must be logged:**
```sql
-- Log all order placements
INSERT INTO system_events (event_type, severity, message, details, source)
VALUES ('ORDER_PLACED', 'INFO', 'Order placed successfully', 
        '{"epic":"BTCUSD","side":"BUY","size":"0.01"}', 'mcp_caller');
```

**Log approval decisions:**
```sql
-- Log all approvals/rejections
INSERT INTO system_events (event_type, severity, message, details, source)
VALUES ('TRADE_APPROVED', 'INFO', 'Trade approved by human', 
        '{"intent_id":"intent_123","approver":"admin"}', 'telegram_handler');
```

**Log system changes:**
```sql
-- Log configuration changes
INSERT INTO system_events (event_type, severity, message, details, source)
VALUES ('CONFIG_CHANGED', 'WARN', 'Risk limits updated', 
        '{"old_limit":"0.01","new_limit":"0.02"}', 'admin');
```

### Compliance Requirements

**Retain logs for required period:**
```sql
-- Keep system events for 7 years
CREATE POLICY retain_system_events ON system_events
FOR ALL TO trader
USING (occurred_at > NOW() - INTERVAL '7 years');
```

**Regular log review:**
```bash
# Weekly security review
docker-compose exec db psql -U trader -d trading -c "
SELECT event_type, COUNT(*) as count, MAX(occurred_at) as last_occurrence
FROM system_events 
WHERE occurred_at > NOW() - INTERVAL '7 days'
GROUP BY event_type
ORDER BY count DESC;"
```

## 🚫 Access Control

### User Management

**Principle of least privilege:**
- Database users with minimal required permissions
- n8n users with specific workflow access only
- API users with rate-limited access

**Role-based access:**
```sql
-- Create roles
CREATE ROLE trading_admin;
CREATE ROLE trading_monitor;
CREATE ROLE trading_analyst;

-- Grant permissions
GRANT ALL ON ALL TABLES TO trading_admin;
GRANT SELECT ON ALL TABLES TO trading_monitor;
GRANT SELECT ON trades, performance TO trading_analyst;
```

### API Security

**Rate limiting:**
```python
# In mcp_call.py
MAX_REQUESTS_PER_MINUTE = 100
MIN_CALL_INTERVAL = 0.1  # 100ms between calls
```

**Request validation:**
```python
# Validate all inputs
def validate_order_request(epic, direction, size):
    if not epic or not direction or not size:
        raise ValueError("Missing required parameters")
    
    if direction not in ['BUY', 'SELL']:
        raise ValueError("Invalid direction")
    
    if float(size) <= 0:
        raise ValueError("Invalid size")
```

## 🔐 Encryption

### Data in Transit

**Use HTTPS for all external communications:**
```yaml
# nginx reverse proxy configuration
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:5678;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Encrypt MCP communications:**
```python
# Add TLS to MCP calls
import ssl
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE
```

### Data at Rest

**Encrypt database:**
```bash
# Enable database encryption
docker run -d --name postgres-encrypted \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=trading \
  -v encrypted_data:/var/lib/postgresql/data \
  postgres:16
```

**Encrypt backup files:**
```bash
# Encrypt all backups
tar czf - backup_data | gpg --symmetric --cipher-algo AES256 --output backup.tar.gz.gpg
```

## 🚨 Incident Response

### Security Incident Procedures

**1. Immediate Response:**
```bash
# Stop all trading immediately
echo "TRADING_HALTED=1" >> .env
docker-compose restart

# Close all positions
docker-compose exec mcp-caller python /app/scripts/mcp_call.py get_positions
# Manually close each position
```

**2. Investigation:**
```bash
# Check recent system events
docker-compose exec db psql -U trader -d trading -c "
SELECT * FROM system_events 
WHERE occurred_at > NOW() - INTERVAL '1 hour'
ORDER BY occurred_at DESC;"

# Check failed authentications
docker-compose exec db psql -U trader -d trading -c "
SELECT * FROM system_events 
WHERE event_type = 'AUTH_FAILURE'
AND occurred_at > NOW() - INTERVAL '24 hours';"
```

**3. Containment:**
- Isolate affected systems
- Change all passwords and API keys
- Review and rotate approval secrets
- Check for unauthorized access

**4. Recovery:**
- Restore from clean backup if needed
- Update all security configurations
- Implement additional monitoring
- Document lessons learned

### Emergency Contacts

**Create incident response plan:**
```bash
# emergency_contacts.txt
Security Team: security@yourdomain.com
Trading Team: trading@yourdomain.com
IT Support: support@yourdomain.com
Capital.com Support: support@capital.com
```

## 🔍 Security Testing

### Regular Security Audits

**Monthly security checklist:**
- [ ] Review system events for anomalies
- [ ] Check for failed authentications
- [ ] Verify API key rotation
- [ ] Test backup and recovery procedures
- [ ] Review user access permissions
- [ ] Check for unauthorized configuration changes

**Penetration testing:**
```bash
# Test network security
nmap -sS -O localhost
nmap -sV -p 5678,5432 localhost

# Test API endpoints
curl -X POST http://localhost:5678/webhook/test
```

### Vulnerability Management

**Regular updates:**
```bash
# Update Docker images
docker-compose pull
docker-compose up -d

# Update Python packages
docker-compose exec mcp-caller pip list --outdated
docker-compose exec mcp-caller pip install --upgrade package_name
```

**Security scanning:**
```bash
# Scan for vulnerabilities
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image capital-mcp-server:latest
```

## 📋 Security Checklist

### Initial Setup
- [ ] Change all default passwords
- [ ] Generate strong approval secret
- [ ] Enable 2FA on Capital.com
- [ ] Configure firewall rules
- [ ] Set up monitoring alerts
- [ ] Encrypt sensitive data
- [ ] Create backup procedures

### Ongoing Maintenance
- [ ] Weekly security log review
- [ ] Monthly password rotation
- [ ] Quarterly security audit
- [ ] Annual penetration testing
- [ ] Regular backup testing
- [ ] Update security documentation

### Incident Response
- [ ] Emergency contact list
- [ ] Incident response procedures
- [ ] Recovery procedures documented
- [ ] Communication plan
- [ ] Post-incident review process

## 📞 Security Support

**For security issues:**
- Email: security@yourdomain.com
- Phone: +1-XXX-XXX-XXXX
- Emergency: +1-XXX-XXX-XXXX

**Report vulnerabilities:**
- Use responsible disclosure
- Include detailed reproduction steps
- Provide impact assessment
- Allow reasonable time for fixes

## 📄 Compliance

### Regulatory Requirements

**Financial regulations:**
- Maintain audit trails for 7 years
- Implement proper access controls
- Regular security assessments
- Incident reporting procedures

**Data protection:**
- Encrypt personal data
- Implement data retention policies
- Regular data purging
- User consent management

### Documentation

**Required documentation:**
- Security policy
- Incident response plan
- Access control procedures
- Backup and recovery procedures
- User training materials

## ⚠️ Disclaimer

This security guide provides general guidance for securing the trading automation stack. Security requirements may vary based on your specific use case, regulatory environment, and risk tolerance. Always consult with security professionals and legal advisors for your specific situation.

**Security is an ongoing process, not a one-time setup.**
