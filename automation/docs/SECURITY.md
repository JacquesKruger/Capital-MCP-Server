# Security Guidelines for Trading Automation Stack

## 🔴 CRITICAL SECURITY NOTICE

Automated trading systems handle real money and sensitive credentials. **Security breaches can result in financial loss, unauthorized trades, or stolen credentials.**

Follow these guidelines rigorously.

---

## 🔐 Authentication & Credentials

### API Keys

**Capital.com API Keys:**
- Store in environment variables ONLY (never hardcode)
- Use separate demo and live credentials
- Rotate keys every 90 days
- Revoke immediately if compromised
- Never commit to Git (verify `.gitignore`)
- Use strong, unique passwords (min 16 chars)

**Storage:**
```bash
# GOOD: Environment variables
export CAP_API_KEY="your_key_here"

# BAD: Hardcoded in scripts
api_key = "abc123..."  # NEVER DO THIS
```

### Database Credentials

- Use strong passwords (min 16 chars, alphanumeric + special)
- Change default credentials immediately
- Restrict PostgreSQL access to Docker network only
- Never expose port 5432 to public internet
- Use least-privilege principle for DB users

### n8n Access

- Enable basic auth: `N8N_BASIC_AUTH_ACTIVE=true`
- Use strong password for n8n admin
- Consider IP whitelist for n8n UI (reverse proxy)
- Use HTTPS in production (Let's Encrypt)
- Enable 2FA if available

### AI Provider Keys

- Protect OpenAI/Anthropic API keys
- Set usage limits/budgets
- Monitor API usage for anomalies
- Rotate keys periodically

---

## 🛡️ Network Security

### Docker Network Isolation

```yaml
# docker-compose.yml - all services on private network
networks:
  trading-net:
    driver: bridge
```

- Services communicate via internal Docker network
- Only n8n port (5678) exposed to host
- PostgreSQL not exposed to host (or bind to 127.0.0.1 only)

### Firewall Rules

```bash
# Allow only necessary ports
sudo ufw allow 5678/tcp  # n8n (or restrict to VPN)
sudo ufw deny 5432/tcp   # PostgreSQL (internal only)
sudo ufw enable
```

### TLS/SSL

**Production deployment:**
- Use reverse proxy (nginx, Caddy)
- Obtain SSL certificate (Let's Encrypt)
- Enforce HTTPS for n8n UI
- Configure secure headers

**Example nginx config:**
```nginx
server {
    listen 443 ssl http2;
    server_name n8n.yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/n8n.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/n8n.yourdomain.com/privkey.pem;
    
    location / {
        proxy_pass http://localhost:5678;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 🔑 Approval & Authorization

### HMAC Approval Tokens

All order executions require HMAC-signed approval tokens:

```python
# Generate token
message = f"{epic}:{direction}:{size}"
token = hmac.new(APPROVAL_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()

# Token is valid for 5 minutes
```

**Security properties:**
- Tokens cannot be forged without `APPROVAL_SECRET`
- Tokens are specific to trade parameters (epic, direction, size)
- Tokens expire after 5 minutes
- Token verification is constant-time (prevents timing attacks)

**Best practices:**
- Use strong `APPROVAL_SECRET` (min 32 random chars)
- Generate via: `openssl rand -hex 32`
- Rotate secret periodically (invalidates old tokens)

### Multi-Level Authorization

1. **Signal Generation** → Requires valid indicator data
2. **Intent Creation** → Requires passing risk checks
3. **AI Review** (optional) → Sanity check by LLM
4. **Human Approval** (optional) → Manual verification
5. **Token Generation** → HMAC signature
6. **Order Execution** → Token verification + final risk check

---

## 🚨 Risk Controls

### Kill Switch

**Immediate halt:**
```bash
# In .env
TRADING_HALTED=1
```

Restart containers to apply:
```bash
docker-compose restart mcp-caller n8n
```

**Effect:**
- All new order attempts blocked
- Existing positions unaffected
- Can still close positions manually

### Daily Loss Limits

Configured in `config/risk.yaml`:
```yaml
account_risk:
  daily_loss_limit_pct: 3.0
  daily_loss_limit_usd: 150
```

**Enforcement:**
- Checked before every order
- Halts trading if exceeded
- Alerts sent to admin
- Requires manual reset next day

### Position Limits

```yaml
account_risk:
  max_open_positions: 5
  max_positions_per_instrument: 1
  max_risk_per_trade_pct: 1.0
```

**Prevents:**
- Over-concentration
- Excessive risk exposure
- Runaway order generation

### Rate Limiting

`mcp_call.py` enforces:
- Max 100 API calls per minute
- 100ms minimum between calls
- Exponential backoff on errors
- Circuit breaker on repeated failures

**Prevents:**
- API rate limit violations
- Accidental DDoS
- Runaway loops

---

## 📊 Monitoring & Alerting

### System Events Log

All critical actions logged to `system_events` table:
- Order placements
- Trade closures
- Errors and warnings
- Risk limit breaches
- AI review results

**Query recent events:**
```sql
SELECT * FROM system_events 
WHERE severity IN ('WARNING', 'CRITICAL')
  AND occurred_at > NOW() - INTERVAL '24 hours'
ORDER BY occurred_at DESC;
```

### Alert Thresholds

Configure in `config/risk.yaml`:
```yaml
monitoring:
  alerts:
    - condition: "daily_loss_pct > 2"
      severity: "warning"
      action: "notify"
    - condition: "daily_loss_pct > 3"
      severity: "critical"
      action: "halt_trading"
```

### Notifications

**Email alerts:**
```bash
# Configure SMTP in n8n
# Workflow D sends daily summary + critical alerts
```

**SMS alerts (optional):**
- Twilio integration
- Send on critical events only
- Avoid alert fatigue

### Audit Trail

**Complete audit log:**
- Every signal stored
- Every intent recorded
- Every order tracked
- AI reviews preserved
- Performance calculated

**Compliance:**
- Retain logs for regulatory requirements
- Timestamped and immutable
- Can reconstruct any trade decision

---

## 🔒 Data Protection

### Secrets Management

**Docker Secrets (production):**
```yaml
# docker-compose.yml
services:
  mcp-caller:
    secrets:
      - cap_api_key
      - cap_password

secrets:
  cap_api_key:
    file: ./secrets/cap_api_key.txt
  cap_password:
    file: ./secrets/cap_password.txt
```

**Environment Variables (development):**
- Use `.env` file (git-ignored)
- Never commit `.env` to repository
- Use `.env.example` as template

### Database Encryption

**At-rest encryption:**
- Enable PostgreSQL SSL: `ssl = on` in `postgresql.conf`
- Encrypt Docker volumes (LUKS, dm-crypt)
- Full-disk encryption for host

**In-transit encryption:**
- Use SSL connections: `sslmode=require`
- Configure in connection strings

### Backup Security

**Encrypted backups:**
```bash
# Backup with encryption
docker-compose exec db pg_dump -U trader trading | \
  gpg --symmetric --cipher-algo AES256 > backup_$(date +%Y%m%d).sql.gpg

# Restore
gpg --decrypt backup_20250108.sql.gpg | \
  docker-compose exec -T db psql -U trader trading
```

**Backup storage:**
- Store off-site (S3, encrypted)
- Restrict access (IAM policies)
- Test restore procedures regularly

---

## 🐛 Vulnerability Management

### Dependency Updates

**Python packages:**
```bash
# Check for vulnerabilities
pip list --outdated

# Update packages
pip install --upgrade -r requirements-automation.txt
```

**Docker images:**
```bash
# Pull latest base images
docker pull postgres:16-alpine
docker pull python:3.11-slim
docker pull n8nio/n8n:latest

# Rebuild
docker-compose build --no-cache
```

**Security scanning:**
```bash
# Scan Docker images
docker scan capital-mcp-server:latest
docker scan mcp-caller:latest
```

### Code Review

- Review all custom scripts for security issues
- Validate user inputs rigorously
- Use parameterized SQL queries (prevent SQL injection)
- Escape shell commands (prevent command injection)
- Follow principle of least privilege

### Penetration Testing

**Before production:**
- Test for SQL injection
- Test for command injection
- Test authentication bypass
- Test rate limiting
- Test error handling

---

## 🚑 Incident Response

### Security Incident Checklist

1. **Detect:**
   - Monitor system events for anomalies
   - Check for unauthorized access
   - Review unusual trade activity

2. **Contain:**
   - Activate kill switch: `TRADING_HALTED=1`
   - Close all open positions
   - Disable n8n workflows
   - Stop Docker containers if necessary

3. **Investigate:**
   - Review system events log
   - Check database for unauthorized changes
   - Analyze n8n execution logs
   - Review MCP server logs

4. **Eradicate:**
   - Rotate all API keys immediately
   - Change all passwords
   - Update `APPROVAL_SECRET`
   - Patch vulnerabilities

5. **Recover:**
   - Restore from clean backup if necessary
   - Verify system integrity
   - Resume trading cautiously (demo first)

6. **Post-Incident:**
   - Document incident timeline
   - Identify root cause
   - Implement preventive measures
   - Update security procedures

### Emergency Contacts

**Maintain list of:**
- System administrator
- Capital.com support
- Security team (if applicable)
- Legal/compliance (if applicable)

### Breach Notification

If credentials are compromised:
1. Contact Capital.com support immediately
2. Revoke API keys via web interface
3. Change account password
4. Enable 2FA if not already enabled
5. Review account activity for unauthorized trades

---

## ✅ Security Checklist

### Pre-Deployment

- [ ] Strong passwords for all services (min 16 chars)
- [ ] `APPROVAL_SECRET` generated (min 32 random chars)
- [ ] `.env` file NOT committed to Git
- [ ] `.gitignore` includes `secrets/`, `.env`
- [ ] Docker network isolated (not host mode)
- [ ] PostgreSQL port NOT exposed publicly
- [ ] n8n basic auth enabled
- [ ] Demo environment confirmed (`CAP_ENVIRONMENT=demo`)
- [ ] Risk limits configured conservatively
- [ ] Kill switch tested (`TRADING_HALTED=1`)
- [ ] Emergency procedures documented
- [ ] Backup/restore tested
- [ ] Logs monitored (system_events)

### Production

- [ ] TLS/SSL certificate installed
- [ ] Reverse proxy configured (nginx/Caddy)
- [ ] Firewall rules applied (ufw/iptables)
- [ ] IP whitelist for n8n access
- [ ] VPN required for admin access
- [ ] 2FA enabled on Capital.com account
- [ ] API keys rotated (separate from demo)
- [ ] Usage limits set on AI provider
- [ ] Monitoring/alerting configured
- [ ] Daily backups automated
- [ ] Incident response plan ready
- [ ] Compliance requirements met

### Ongoing

- [ ] Weekly review of system events
- [ ] Monthly password/key rotation
- [ ] Quarterly security audit
- [ ] Update dependencies regularly
- [ ] Test backup/restore monthly
- [ ] Review trade decisions for anomalies
- [ ] Monitor account balance daily

---

## 📚 Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/security.html)
- [n8n Security](https://docs.n8n.io/hosting/security/)
- [Capital.com API Documentation](https://open-api.capital.com/)

---

## 🆘 Report Security Issues

**DO NOT** open public GitHub issues for security vulnerabilities.

**Instead:**
- Email: security@yourdomain.com (replace with actual contact)
- Include: Detailed description, steps to reproduce, impact assessment
- Allow reasonable time for fix before public disclosure

---

## 📄 License

See `../LICENSE`

---

**Remember:** Security is not a one-time task but an ongoing process. Stay vigilant, keep systems updated, and never compromise on security for convenience.

