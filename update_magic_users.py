#!/usr/bin/env python
"""
Script to update Magic Users table with Auth Users data and generate magic links

This script performs the following tasks:
1. Checks all users in the auth_user table
2. Creates or updates records in magic_users table for each user
3. Generates magic links and tokens
4. Updates webhook sending status
"""

import os
import sys
import django
from datetime import datetime, timedelta
from django.utils import timezone

# Load Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'farmon.settings')
django.setup()

from apps.authentication.models import User, MagicUser
from django.conf import settings

def update_magic_users_from_auth_users():
    """
    Create/update magic_users records for all users in auth_user table
    """
    print("Starting Magic Users table update...")
    
    # Get all auth_user users
    all_users = User.objects.all()
    print(f"Found {all_users.count()} total users")
    
    updated_count = 0
    created_count = 0
    error_count = 0
    
    for user in all_users:
        try:
            # Check if magic_user record exists for user
            magic_user, created = MagicUser.objects.get_or_create(
                email=user.email,
                defaults={
                    'first_name': user.first_name or 'User',
                    'last_name': user.last_name or 'Name',
                    'company_name': getattr(user, 'company_name', None),
                    'phone_number': user.phone_number,
                    'title': user.title,
                    'position': user.position,
                    'magic_token': MagicUser.generate_magic_token(),
                    'generated_username': MagicUser.generate_username(
                        user.first_name or 'User', 
                        user.email
                    ),
                    'generated_password': MagicUser.generate_password(),
                    'expires_at': timezone.now() + timedelta(days=7),  # Valid for 7 days
                    'is_account_created': True,
                    'created_user': user,
                    'webhook_sent': False,  # Webhook needs to be sent
                }
            )
            
            if created:
                # Generate magic link
                frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
                magic_user.magic_link = f"{frontend_url}/magic-login?token={magic_user.magic_token}"
                magic_user.save()
                
                created_count += 1
                print(f"✓ New magic_user created: {user.email}")
            else:
                # Update existing magic_user
                # Generate new token if current one is expired
                if magic_user.is_expired():
                    magic_user.magic_token = MagicUser.generate_magic_token()
                    magic_user.expires_at = timezone.now() + timedelta(days=7)
                    magic_user.is_used = False
                    
                    # Update magic link
                    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
                    magic_user.magic_link = f"{frontend_url}/magic-login?token={magic_user.magic_token}"
                
                # Update data
                magic_user.first_name = user.first_name or magic_user.first_name
                magic_user.last_name = user.last_name or magic_user.last_name
                magic_user.phone_number = user.phone_number or magic_user.phone_number
                magic_user.title = user.title or magic_user.title
                magic_user.position = user.position or magic_user.position
                magic_user.is_account_created = True
                magic_user.created_user = user
                magic_user.webhook_sent = False  # Webhook needs to be resent
                
                magic_user.save()
                updated_count += 1
                print(f"✓ Magic_user updated: {user.email}")
                
        except Exception as e:
            error_count += 1
            print(f"✗ Error for {user.email}: {str(e)}")
    
    print("\n=== RESULTS ===")
    print(f"Created: {created_count}")
    print(f"Updated: {updated_count}")
    print(f"Errors: {error_count}")
    print(f"Total processed: {created_count + updated_count}")

def generate_magic_links_for_all():
    """
    Generate magic links for all magic_users
    """
    print("\nGenerating magic links for all magic_users...")
    
    magic_users = MagicUser.objects.all()
    print(f"Found {magic_users.count()} total magic_users")
    
    updated_count = 0
    error_count = 0
    
    for magic_user in magic_users:
        try:
            # Generate new token if missing or expired
            if not magic_user.magic_token or magic_user.is_expired():
                magic_user.magic_token = MagicUser.generate_magic_token()
                magic_user.expires_at = timezone.now() + timedelta(days=7)
                magic_user.is_used = False
            
            # Generate magic link
            frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
            magic_user.magic_link = f"{frontend_url}/magic-login?token={magic_user.magic_token}"
            magic_user.webhook_sent = False  # Webhook needs to be resent
            magic_user.save()
            
            updated_count += 1
            print(f"✓ Magic link updated: {magic_user.email}")
            
        except Exception as e:
            error_count += 1
            print(f"✗ Error for {magic_user.email}: {str(e)}")
    
    print("\n=== RESULTS ===")
    print(f"Updated: {updated_count}")
    print(f"Errors: {error_count}")

def show_statistics():
    """
    Show Magic Users statistics
    """
    print("\n=== MAGIC USERS STATISTICS ===")
    
    total_magic_users = MagicUser.objects.count()
    active_magic_users = MagicUser.objects.filter(expires_at__gt=timezone.now(), is_used=False).count()
    expired_magic_users = MagicUser.objects.filter(expires_at__lte=timezone.now()).count()
    used_magic_users = MagicUser.objects.filter(is_used=True).count()
    account_created = MagicUser.objects.filter(is_account_created=True).count()
    webhook_sent = MagicUser.objects.filter(webhook_sent=True).count()
    
    print(f"Total magic users: {total_magic_users}")
    print(f"Active magic users: {active_magic_users}")
    print(f"Expired: {expired_magic_users}")
    print(f"Used: {used_magic_users}")
    print(f"Account created: {account_created}")
    print(f"Webhook sent: {webhook_sent}")
    
    # Latest 5 magic users
    print("\n=== LATEST 5 MAGIC USERS ===")
    recent_users = MagicUser.objects.order_by('-created_at')[:5]
    for user in recent_users:
        status = "Active" if not user.is_expired() and not user.is_used else "Inactive"
        print(f"- {user.email} ({status}) - {user.created_at.strftime('%Y-%m-%d %H:%M')}")

def main():
    """
    Main function
    """
    print("MAGIC USERS UPDATE SCRIPT")
    print("=" * 50)
    
    try:
        # 1. Show statistics
        show_statistics()
        
        # 2. Ask for user confirmation
        print("\nDo you want to perform the following operations?")
        print("1. Update magic_users table with auth_users data")
        print("2. Generate new magic links for all magic_users")
        
        choice = input("\nDo you want to continue? (y/n): ").lower().strip()
        
        if choice in ['y', 'yes']:
            # 3. Update magic users table
            update_magic_users_from_auth_users()
            
            # 4. Generate magic links
            generate_magic_links_for_all()
            
            # 5. Final statistics
            show_statistics()
            
            print("\n✅ All operations completed successfully!")
        else:
            print("\n❌ Operation cancelled.")
            
    except Exception as e:
        print(f"\n❌ General error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()