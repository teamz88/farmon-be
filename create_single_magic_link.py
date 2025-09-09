#!/usr/bin/env python
"""
Script to create magic link for a single user

Usage:
python create_single_magic_link.py user@example.com"""

import os
import sys
import django
from datetime import timedelta
from django.utils import timezone

# Load Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'farmon.settings')
django.setup()

from apps.authentication.models import User, MagicUser
from django.conf import settings

def create_magic_link_for_user(email):
    """
    Create magic link for a specific user
    """
    try:
        # Find user
        try:
            user = User.objects.get(email=email)
            print(f"✓ User found: {user.email}")
        except User.DoesNotExist:
            print(f"✗ User not found: {email}")
            return None
        
        # Create or update magic user
        magic_user, created = MagicUser.objects.get_or_create(
            email=user.email,
            defaults={
                'first_name': user.first_name or 'User',
                'last_name': user.last_name or 'Name',
                'phone_number': user.phone_number,
                'title': user.title,
                'position': user.position,
                'magic_token': MagicUser.generate_magic_token(),
                'generated_username': MagicUser.generate_username(
                    user.first_name or 'User', 
                    user.email
                ),
                'generated_password': MagicUser.generate_password(),
                'expires_at': timezone.now() + timedelta(days=7),
                'is_account_created': True,
                'created_user': user,
                'webhook_sent': False,
            }
        )
        
        if not created:
            # Generate new token for existing magic_user
            magic_user.magic_token = MagicUser.generate_magic_token()
            magic_user.expires_at = timezone.now() + timedelta(days=7)
            magic_user.is_used = False
            magic_user.webhook_sent = False
        
        # Generate magic link
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        magic_user.magic_link = f"{frontend_url}/magic-login?token={magic_user.magic_token}"
        magic_user.save()
        
        action = "created" if created else "updated"
        print(f"✓ Magic link {action}!")
        print(f"\n=== MAGIC LINK INFORMATION ===")
        print(f"Email: {magic_user.email}")
        print(f"Name: {magic_user.first_name} {magic_user.last_name}")
        print(f"Token: {magic_user.magic_token}")
        print(f"Magic Link: {magic_user.magic_link}")
        print(f"Expires at: {magic_user.expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Username: {magic_user.generated_username}")
        
        return magic_user
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return None

def main():
    if len(sys.argv) != 2:
        print("Usage: python create_single_magic_link.py <email>")
        print("Example: python create_single_magic_link.py user@example.com")
        sys.exit(1)
    
    email = sys.argv[1]
    
    print(f"Creating magic link for: {email}")
    print("=" * 50)
    
    magic_user = create_magic_link_for_user(email)
    
    if magic_user:
        print("\n✅ Magic link created successfully!")
        
        # Webhook sending reminder
        print("\n📝 NOTE:")
        print("- Magic link created, but webhook not sent yet")
        print("- Use MagicLinkRegistrationView to send webhook")
        print("- Or manually set webhook_sent=True")
    else:
        print("\n❌ Error occurred while creating magic link")
        sys.exit(1)

if __name__ == '__main__':
    main()