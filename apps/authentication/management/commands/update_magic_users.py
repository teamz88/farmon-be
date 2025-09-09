from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from apps.authentication.models import User, MagicUser


class Command(BaseCommand):
    help = 'Update Magic Users table with Auth Users data and generate magic links'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Execute without confirmation',
        )
        parser.add_argument(
            '--regenerate-all',
            action='store_true',
            help='Regenerate all magic links',
        )
        parser.add_argument(
            '--stats-only',
            action='store_true',
            help='Show statistics only',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('MAGIC USERS UPDATE SCRIPT')
        )
        self.stdout.write('=' * 50)

        # Show statistics only
        if options['stats_only']:
            self.show_statistics()
            return

        # Show statistics
        self.show_statistics()

        # Confirmation (if --force is not used)
        if not options['force']:
            self.stdout.write('\nDo you want to perform the following operations?')
            self.stdout.write('1. Update magic_users table with auth_users data')
            if options['regenerate_all']:
                self.stdout.write('2. Generate new magic links for all magic_users')
            
            confirm = input('\nDo you want to continue? (y/n): ').lower().strip()
            if confirm not in ['y', 'yes']:
                self.stdout.write(
                    self.style.WARNING('❌ Operation cancelled.')
                )
                return

        try:
            # Update magic users table
            self.update_magic_users_from_auth_users()

            # If --regenerate-all flag is provided
            if options['regenerate_all']:
                self.generate_magic_links_for_all()

            # Final statistics
            self.show_statistics()

            self.stdout.write(
                self.style.SUCCESS('\n✅ All operations completed successfully!')
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ General error: {str(e)}')
            )
            raise

    def update_magic_users_from_auth_users(self):
        """
        Create/update magic_users records for all users in auth_user table
        """
        self.stdout.write('Starting Magic Users table update...')
        
        # Get all auth_user users
        all_users = User.objects.all()
        self.stdout.write(f'Found {all_users.count()} total users')
        
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
                        'is_account_created': True,  # Already created
                        'created_user': user,
                        'webhook_sent': False,  # Webhook needs to be resent
                    }
                )
                
                if created:
                    # New magic_user created
                    # Generate magic link
                    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
                    magic_user.magic_link = f"{frontend_url}/magic-link/set-password?token={magic_user.magic_token}"
                    magic_user.save()
                    
                    created_count += 1
                    self.stdout.write(f'✓ New magic_user created: {user.email}')
                else:
                    # Existing magic_user updated
                    # Generate new token if expired or missing
                    if magic_user.is_expired() or not magic_user.magic_token:
                        magic_user.magic_token = MagicUser.generate_magic_token()
                        magic_user.expires_at = timezone.now() + timedelta(days=7)
                        
                        # Update magic link
                        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
                        magic_user.magic_link = f"{frontend_url}/magic-link/set-password?token={magic_user.magic_token}"
                    
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
                    self.stdout.write(f'✓ Magic_user updated: {user.email}')
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'✗ Error for {user.email}: {str(e)}')
                )
        
        self.stdout.write('\n=== RESULTS ===')
        self.stdout.write(f'Created: {created_count}')
        self.stdout.write(f'Updated: {updated_count}')
        self.stdout.write(f'Errors: {error_count}')
        self.stdout.write(f'Total processed: {created_count + updated_count}')

    def generate_magic_links_for_all(self):
        """
        Generate new magic links for all magic_users
        """
        self.stdout.write('\nGenerating magic links for all magic_users...')
        
        magic_users = MagicUser.objects.all()
        self.stdout.write(f'Found {magic_users.count()} total magic_users')
        
        updated_count = 0
        
        for magic_user in magic_users:
            try:
                # Generate new token
                magic_user.magic_token = MagicUser.generate_magic_token()
                magic_user.expires_at = timezone.now() + timedelta(days=7)
                
                # Update magic link
                frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
                magic_user.magic_link = f"{frontend_url}/magic-link/set-password?token={magic_user.magic_token}"
                
                # Reset webhook status
                magic_user.webhook_sent = False
                magic_user.is_used = False
                
                magic_user.save()
                updated_count += 1
                
                self.stdout.write(f'✓ Magic link updated: {magic_user.email}')
                self.stdout.write(f'  Token: {magic_user.magic_token}')
                self.stdout.write(f'  Link: {magic_user.magic_link}')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error for {magic_user.email}: {str(e)}')
                )
        
        self.stdout.write(f'\nTotal {updated_count} magic links updated')

    def show_statistics(self):
        """
        Show Magic Users statistics
        """
        self.stdout.write('\n=== MAGIC USERS STATISTICS ===')
        
        total_magic_users = MagicUser.objects.count()
        active_magic_users = MagicUser.objects.filter(
            expires_at__gt=timezone.now(), 
            is_used=False
        ).count()
        expired_magic_users = MagicUser.objects.filter(
            expires_at__lte=timezone.now()
        ).count()
        used_magic_users = MagicUser.objects.filter(is_used=True).count()
        account_created = MagicUser.objects.filter(is_account_created=True).count()
        webhook_sent = MagicUser.objects.filter(webhook_sent=True).count()
        
        self.stdout.write(f'Total magic users: {total_magic_users}')
        self.stdout.write(f'Active magic users: {active_magic_users}')
        self.stdout.write(f'Expired: {expired_magic_users}')
        self.stdout.write(f'Used: {used_magic_users}')
        self.stdout.write(f'Account created: {account_created}')
        self.stdout.write(f'Webhook sent: {webhook_sent}')
        
        # Latest 5 magic users
        self.stdout.write('\n=== LATEST 5 MAGIC USERS ===')
        recent_users = MagicUser.objects.order_by('-created_at')[:5]
        for user in recent_users:
            status = "Active" if not user.is_expired() and not user.is_used else "Inactive"
            self.stdout.write(
                f'- {user.email} ({status}) - {user.created_at.strftime("%Y-%m-%d %H:%M")}'
            )