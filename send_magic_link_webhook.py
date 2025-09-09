#!/usr/bin/env python
"""
Script to send magic link emails and user data to N8N

This script performs the following tasks:
1. Gets data from Magic Users table
2. Sends email and user data to N8N webhook
3. Updates webhook sending status
4. Monitors email sending results
"""

import os
import sys
import django
import requests
import json
from datetime import datetime

# Load Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'farmon.settings')
django.setup()

from apps.authentication.models import MagicUser
from django.conf import settings
from django.utils import timezone

def get_webhook_url():
    """
    Get N8N webhook URL
    """
    webhook_url = getattr(settings, 'N8N_WEBHOOK_URL', None)
    if not webhook_url:
        print("❌ N8N_WEBHOOK_URL environment variable not set!")
        print("Run the following command:")
        print("export N8N_WEBHOOK_URL='https://your-n8n-instance.com/webhook/magic-link'")
        return None
    return webhook_url

def prepare_webhook_data(magic_user):
    """
    Prepare data for webhook
    """
    return {
        'user_id': str(magic_user.id),
        'email': magic_user.email,
        'first_name': magic_user.first_name,
        'last_name': magic_user.last_name,
        'full_name': f"{magic_user.first_name} {magic_user.last_name}",
        'company_name': magic_user.company_name or '',
        'phone_number': magic_user.phone_number or '',
        'title': magic_user.title or '',
        'position': magic_user.position or '',
        'magic_link': magic_user.magic_link,
        'magic_token': magic_user.magic_token,
        'expires_at': magic_user.expires_at.isoformat(),
        'created_at': magic_user.created_at.isoformat(),
        'generated_username': magic_user.generated_username,
        'is_account_created': magic_user.is_account_created,
        'webhook_type': 'magic_link_registration',
        'timestamp': timezone.now().isoformat()
    }

def send_webhook_to_n8n(magic_user, webhook_url):
    """
    Send webhook to N8N
    """
    try:
        # Prepare data
        webhook_data = prepare_webhook_data(magic_user)
        
        print(f"📤 Sending webhook: {magic_user.email}")
        print(f"   URL: {webhook_url}")
        
        # Send webhook
        response = requests.post(
            webhook_url,
            json=webhook_data,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Farmon-Magic-Link-Sender/1.0'
            },
            timeout=30
        )
        
        # Check response
        if response.status_code == 200:
            print(f"✅ Webhook sent successfully: {magic_user.email}")
            
            # Update webhook status
            magic_user.webhook_sent = True
            magic_user.webhook_sent_at = timezone.now()
            magic_user.save(update_fields=['webhook_sent', 'webhook_sent_at'])
            
            return True, "Successfully sent"
        else:
            error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
            print(f"❌ Error sending webhook: {error_msg}")
            return False, error_msg
            
    except requests.exceptions.Timeout:
        error_msg = "Timeout error sending webhook"
        print(f"❌ {error_msg}")
        return False, error_msg
        
    except requests.exceptions.ConnectionError:
        error_msg = "Error connecting to N8N server"
        print(f"❌ {error_msg}")
        return False, error_msg
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg

def send_webhooks_for_pending_users():
    """
    Send webhooks for all magic users who haven't had webhooks sent
    """
    webhook_url = get_webhook_url()
    if not webhook_url:
        return
    
    # Find magic users without webhooks sent
    pending_users = MagicUser.objects.filter(
        webhook_sent=False,
        expires_at__gt=timezone.now()  # Only active links
    ).order_by('-created_at')
    
    print(f"📋 Users who need webhooks sent: {pending_users.count()}")
    
    if pending_users.count() == 0:
        print("✅ Webhooks already sent for all active magic users")
        return
    
    success_count = 0
    error_count = 0
    
    for magic_user in pending_users:
        success, message = send_webhook_to_n8n(magic_user, webhook_url)
        
        if success:
            success_count += 1
        else:
            error_count += 1
            print(f"   Error: {message}")
    
    print(f"\n=== WEBHOOK SENDING RESULTS ===")
    print(f"Successful: {success_count}")
    print(f"Errors: {error_count}")
    print(f"Total: {success_count + error_count}")

def send_webhook_for_specific_user(email):
    """
    Send webhook for a specific user
    """
    webhook_url = get_webhook_url()
    if not webhook_url:
        return
    
    try:
        magic_user = MagicUser.objects.get(email=email)
        print(f"📋 User found: {email}")
        
        # Send webhook
        success, message = send_webhook_to_n8n(magic_user, webhook_url)
        
        if success:
            print(f"✅ Webhook sent successfully: {email}")
        else:
            print(f"❌ Error sending webhook: {message}")
            
    except MagicUser.DoesNotExist:
        print(f"❌ User not found: {email}")
        print("Create magic link first:")
        print(f"python create_single_magic_link.py {email}")

def resend_failed_webhooks():
    """
    Resend webhooks for users with failed webhook attempts
    """
    webhook_url = get_webhook_url()
    if not webhook_url:
        return
    
    # Magic users without webhooks sent or not expired
    failed_users = MagicUser.objects.filter(
        webhook_sent=False,
        expires_at__gt=timezone.now()
    ).order_by('-created_at')
    
    print(f"📋 Webhooks that need to be resent: {failed_users.count()}")
    
    if failed_users.count() == 0:
        print("✅ No webhooks need to be resent")
        return
    
    success_count = 0
    error_count = 0
    
    for magic_user in failed_users:
        print(f"🔄 Resending: {magic_user.email}")
        success, message = send_webhook_to_n8n(magic_user, webhook_url)
        
        if success:
            success_count += 1
        else:
            error_count += 1
            print(f"   Error: {message}")
    
    print(f"\n=== RESEND RESULTS ===")
    print(f"Successful: {success_count}")
    print(f"Errors: {error_count}")
    print(f"Total: {success_count + error_count}")

def show_webhook_statistics():
    """
    Show webhook statistics
    """
    print("\n=== WEBHOOK STATISTICS ===")
    
    total_users = MagicUser.objects.count()
    webhook_sent = MagicUser.objects.filter(webhook_sent=True).count()
    webhook_pending = MagicUser.objects.filter(
        webhook_sent=False,
        expires_at__gt=timezone.now()
    ).count()
    expired_users = MagicUser.objects.filter(
        expires_at__lte=timezone.now()
    ).count()
    
    print(f"Total magic users: {total_users}")
    print(f"Webhooks sent: {webhook_sent}")
    print(f"Webhooks pending: {webhook_pending}")
    print(f"Expired users: {expired_users}")
    
    # Recent webhook sent users
    print("\n=== RECENT WEBHOOK SENT USERS ===")
    recent_webhooks = MagicUser.objects.filter(
        webhook_sent=True,
        webhook_sent_at__isnull=False
    ).order_by('-webhook_sent_at')[:5]
    
    for user in recent_webhooks:
        print(f"- {user.email} - {user.webhook_sent_at.strftime('%Y-%m-%d %H:%M:%S')}")

def test_webhook_connection():
    """
    Test N8N webhook connection
    """
    webhook_url = get_webhook_url()
    if not webhook_url:
        return
    
    print(f"🔍 Testing N8N webhook connection: {webhook_url}")
    
    # Test data
    test_data = {
        'test': True,
        'message': 'Farmon Magic Link Webhook Test',
        'timestamp': timezone.now().isoformat(),
        'webhook_type': 'connection_test'
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=test_data,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Farmon-Magic-Link-Sender/1.0'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ N8N webhook connection successful!")
            print(f"   Response: {response.text[:100]}")
        else:
            print(f"❌ N8N webhook error: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            
    except Exception as e:
        print(f"❌ Connection error: {str(e)}")

def main():
    """
    Main function
    """
    print("N8N MAGIC LINK WEBHOOK SENDING SCRIPT")
    print("=" * 50)
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python send_magic_link_webhook.py all          # All pending webhooks")
        print("  python send_magic_link_webhook.py user@email   # Specific user")
        print("  python send_magic_link_webhook.py resend       # Resend failed ones")
        print("  python send_magic_link_webhook.py stats        # Show statistics")
        print("  python send_magic_link_webhook.py test         # Test connection")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    try:
        if command == 'all':
            show_webhook_statistics()
            print("\n" + "="*30)
            send_webhooks_for_pending_users()
            
        elif command == 'resend':
            show_webhook_statistics()
            print("\n" + "="*30)
            resend_failed_webhooks()
            
        elif command == 'stats':
            show_webhook_statistics()
            
        elif command == 'test':
            test_webhook_connection()
            
        elif '@' in command:  # Email address
            send_webhook_for_specific_user(command)
            
        else:
            print(f"❌ Invalid command: {command}")
            print("Supported commands: all, resend, stats, test, email@domain.com")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ General error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()