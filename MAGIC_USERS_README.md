# Magic Users Update and Webhook Sending Scripts

These scripts are designed to update the `magic_users` table with data from `auth_users`, generate magic links, and send webhooks to N8N.

## Scripts List

### 1. `update_magic_users.py` - Magic Users Update Script

Updates the magic_users table with all auth_users data and generates magic links.

**Usage:**
```bash
cd /Users/bro/PROJECTS/farmon/farmon-be
python update_magic_users.py
```

**Features:**
- Interactive mode (asks for confirmation)
- Creates/updates magic_users for all auth_users
- Generates magic links
- Shows statistics
- Tracks errors

### 2. Django Management Command

**Usage:**
```bash
# Basic usage
python manage.py update_magic_users

# Execute without confirmation
python manage.py update_magic_users --force

# Regenerate all magic links
python manage.py update_magic_users --regenerate-all

# Show statistics only
python manage.py update_magic_users --stats-only

# Combination
python manage.py update_magic_users --force --regenerate-all
```

**Parameters:**
- `--force`: Execute without confirmation
- `--regenerate-all`: Regenerate all magic links
- `--stats-only`: Show statistics only

### 3. `create_single_magic_link.py` - For Single User

Creates a magic link for a specific user.

**Usage:**
```bash
python create_single_magic_link.py user@example.com
```

**Example:**
```bash
python create_single_magic_link.py john.doe@company.com
```

### 4. `send_magic_link_webhook.py` - N8N Webhook Sending Script

Sends magic link data to N8N via webhook.

**Usage:**
```bash
# All pending webhooks
python send_magic_link_webhook.py all

# For specific user
python send_magic_link_webhook.py user@example.com

# Resend failed attempts
python send_magic_link_webhook.py resend

# Show statistics
python send_magic_link_webhook.py stats

# Test connection
python send_magic_link_webhook.py test
```

### 5. Django Management Commands

**Webhook sending:**
```bash
# All pending webhooks
python manage.py send_magic_webhooks --all

# For specific user
python manage.py send_magic_webhooks --email user@example.com

# Resend failed attempts
python manage.py send_magic_webhooks --resend

# Show statistics
python manage.py send_magic_webhooks --stats

# Test connection
python manage.py send_magic_webhooks --test
```

## What Do the Scripts Do?

### Magic Users Creation/Update

1. **Creating new magic_user:**
   - When auth_user exists but magic_user doesn't
   - Copies all necessary data
   - Generates new magic token and link
   - Sets 7-day expiration period

2. **Updating existing magic_user:**
   - Updates data from auth_user
   - Creates new token if current one is expired
   - Resets webhook status

### Magic Link Generation

- Creates new 64-character token
- Forms complete link with frontend URL
- Sets 7-day expiration period
- Resets webhook status

## Important Information

### Environment Variables

Scripts use the following environment variables:
- `FRONTEND_URL`: Frontend URL for magic links (default: `http://localhost:3000`)
- `N8N_WEBHOOK_URL`: N8N webhook URL (required for webhook sending)

**Example:**
```bash
export FRONTEND_URL="https://app.farmon.com"
export N8N_WEBHOOK_URL="https://your-n8n-instance.com/webhook/magic-link"
```

### Magic Link Format

```
{FRONTEND_URL}/magic-login?token={magic_token}
```

**Example:**
```
http://localhost:3000/magic-login?token=abc123def456...
```

### Database Tables

- **auth_user**: Main users table
- **magic_users**: Magic link data table

### Security

- Magic tokens are 64-character random strings
- Each token is unique
- 7-day expiration period
- Becomes inactive after use

## Troubleshooting

### Common Errors

1. **Django settings not found:**
   ```bash
   export DJANGO_SETTINGS_MODULE=farmon.settings
   ```

2. **Database connection error:**
   - Check that database is running
   - Verify database settings in settings.py are correct

3. **FRONTEND_URL not set:**
   ```bash
   export FRONTEND_URL=https://yourdomain.com
   ```

### Logging and Debug

Scripts output the following information:
- Number of created/updated records
- List of errors
- Status for each user
- Statistics data

## Examples

### 1. Create magic links for all users

```bash
# Interactive mode
python update_magic_users.py

# Or Django command
python manage.py update_magic_users --force
```

### 2. View statistics only

```bash
python manage.py update_magic_users --stats-only
```

### 3. For single user

```bash
python create_single_magic_link.py admin@farmon.com
```

### 4. Regenerate all magic links

```bash
python manage.py update_magic_users --regenerate-all --force
```

### 5. Send webhooks to N8N

```bash
# All pending webhooks
python send_magic_link_webhook.py all

# Or Django command
python manage.py send_magic_webhooks --all
```

### 6. Test webhook connection

```bash
python send_magic_link_webhook.py test
```

### 7. Complete process (create magic links + send webhooks)

```bash
# 1. Create magic links
python manage.py update_magic_users --force

# 2. Send webhooks
python manage.py send_magic_webhooks --all
```

## Server Usage

### Production Environment

```bash
# Activate virtual environment
source venv/bin/activate

# Set environment variables
export DJANGO_SETTINGS_MODULE=farmon.settings.production
export FRONTEND_URL=https://app.farmon.com
export N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/magic-link

# Create magic links
python manage.py update_magic_users --force

# Send webhooks
python manage.py send_magic_webhooks --all
```

### Setting up Cron Jobs

For daily magic link updates and webhook sending:

```bash
# crontab -e
# Update magic links daily at 2:00 AM
0 2 * * * cd /path/to/farmon-be && python manage.py update_magic_users --force --regenerate-all

# Send webhooks daily at 2:30 AM
30 2 * * * cd /path/to/farmon-be && python manage.py send_magic_webhooks --all

# Resend failed webhooks every hour
0 * * * * cd /path/to/farmon-be && python manage.py send_magic_webhooks --resend
```

## Security Measures

1. **Backup:** Take database backup before running scripts
2. **Test environment:** Test in development environment first
3. **Log monitoring:** Monitor script results
4. **Access control:** Only admin users should have access to scripts

## Support

If there are issues with scripts:
1. Check log files
2. Check database status
3. Verify environment variables are correct
4. Check Django settings configuration