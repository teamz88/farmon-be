from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from apps.authentication.models import MagicUser
import requests
import json


class Command(BaseCommand):
    help = 'Send magic link emails and user data to N8N'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Send all pending webhooks',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Send webhook for specific user',
        )
        parser.add_argument(
            '--resend',
            action='store_true',
            help='Resend failed webhooks',
        )
        parser.add_argument(
            '--test',
            action='store_true',
            help='Test N8N webhook connection',
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show webhook statistics',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('N8N MAGIC LINK WEBHOOK SENDING')
        )
        self.stdout.write('=' * 50)

        try:
            if options['stats']:
                self.show_webhook_statistics()
            elif options['test']:
                self.test_webhook_connection()
            elif options['all']:
                self.show_webhook_statistics()
                self.stdout.write('\n' + '='*30)
                self.send_webhooks_for_pending_users()
            elif options['resend']:
                self.show_webhook_statistics()
                self.stdout.write('\n' + '='*30)
                self.resend_failed_webhooks()
            elif options['email']:
                self.send_webhook_for_specific_user(options['email'])
            else:
                self.stdout.write(
                    self.style.WARNING('No action specified. Use --help for options.')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ General error: {str(e)}')
            )
            raise

    def get_webhook_url(self):
        """
        Get N8N webhook URL
        """
        webhook_url = getattr(settings, 'N8N_WEBHOOK_URL', None)
        if not webhook_url:
            self.stdout.write(
                self.style.ERROR('❌ N8N_WEBHOOK_URL environment variable not set!')
            )
            self.stdout.write('Run the following command:')
            self.stdout.write('export N8N_WEBHOOK_URL="https://your-n8n-instance.com/webhook/magic-link"')
            return None
        return webhook_url

    def prepare_webhook_data(self, magic_user):
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

    def send_webhook_to_n8n(self, magic_user, webhook_url):
        """
        Send webhook to N8N
        """
        try:
            # Prepare data
            webhook_data = self.prepare_webhook_data(magic_user)
            
            self.stdout.write(f'📤 Sending webhook: {magic_user.email}')
            self.stdout.write(f'   URL: {webhook_url}')
            
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
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Webhook sent successfully: {magic_user.email}')
                )
                
                # Update webhook status
                magic_user.webhook_sent = True
                magic_user.webhook_sent_at = timezone.now()
                magic_user.save(update_fields=['webhook_sent', 'webhook_sent_at'])
                
                return True, "Successfully sent"
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                self.stdout.write(
                    self.style.ERROR(f'❌ Error sending webhook: {error_msg}')
                )
                return False, error_msg
                
        except requests.exceptions.Timeout:
            error_msg = "Timeout error sending webhook"
            self.stdout.write(self.style.ERROR(f'❌ {error_msg}'))
            return False, error_msg
            
        except requests.exceptions.ConnectionError:
            error_msg = "Error connecting to N8N server"
            self.stdout.write(self.style.ERROR(f'❌ {error_msg}'))
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.stdout.write(self.style.ERROR(f'❌ {error_msg}'))
            return False, error_msg

    def send_webhooks_for_pending_users(self):
        """
        Send webhooks for all magic users who haven't had webhooks sent
        """
        webhook_url = self.get_webhook_url()
        if not webhook_url:
            return
        
        # Find magic users without webhooks sent
        pending_users = MagicUser.objects.filter(
            webhook_sent=False,
            expires_at__gt=timezone.now()  # Only active links
        ).order_by('-created_at')
        
        self.stdout.write(f'📋 Users who need webhooks sent: {pending_users.count()}')
        
        if pending_users.count() == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ Webhooks already sent for all active magic users')
            )
            return
        
        success_count = 0
        error_count = 0
        
        for magic_user in pending_users:
            success, message = self.send_webhook_to_n8n(magic_user, webhook_url)
            
            if success:
                success_count += 1
            else:
                error_count += 1
                self.stdout.write(f'   Error: {message}')
        
        self.stdout.write('\n=== WEBHOOK SENDING RESULTS ===')
        self.stdout.write(f'Successful: {success_count}')
        self.stdout.write(f'Errors: {error_count}')
        self.stdout.write(f'Total: {success_count + error_count}')

    def send_webhook_for_specific_user(self, email):
        """
        Send webhook for a specific user
        """
        webhook_url = self.get_webhook_url()
        if not webhook_url:
            return
        
        try:
            magic_user = MagicUser.objects.get(email=email)
            self.stdout.write(f'📋 User found: {email}')
            
            # Send webhook
            success, message = self.send_webhook_to_n8n(magic_user, webhook_url)
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Webhook sent successfully: {email}')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error sending webhook: {message}')
                )
                
        except MagicUser.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ User not found: {email}')
            )
            self.stdout.write('Create magic link first:')
            self.stdout.write(f'python manage.py update_magic_users --email {email}')

    def resend_failed_webhooks(self):
        """
        Resend webhooks for users with failed webhook attempts
        """
        webhook_url = self.get_webhook_url()
        if not webhook_url:
            return
        
        # Magic users without webhooks sent or not expired
        failed_users = MagicUser.objects.filter(
            webhook_sent=False,
            expires_at__gt=timezone.now()
        ).order_by('-created_at')
        
        self.stdout.write(f'📋 Webhooks that need to be resent: {failed_users.count()}')
        
        if failed_users.count() == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ No webhooks need to be resent')
            )
            return
        
        success_count = 0
        error_count = 0
        
        for magic_user in failed_users:
            self.stdout.write(f'🔄 Resending: {magic_user.email}')
            success, message = self.send_webhook_to_n8n(magic_user, webhook_url)
            
            if success:
                success_count += 1
            else:
                error_count += 1
                self.stdout.write(f'   Error: {message}')
        
        self.stdout.write('\n=== RESEND RESULTS ===')
        self.stdout.write(f'Successful: {success_count}')
        self.stdout.write(f'Errors: {error_count}')
        self.stdout.write(f'Total: {success_count + error_count}')

    def show_webhook_statistics(self):
        """
        Show webhook statistics
        """
        self.stdout.write('\n=== WEBHOOK STATISTICS ===')
        
        total_users = MagicUser.objects.count()
        webhook_sent = MagicUser.objects.filter(webhook_sent=True).count()
        webhook_pending = MagicUser.objects.filter(
            webhook_sent=False,
            expires_at__gt=timezone.now()
        ).count()
        expired_users = MagicUser.objects.filter(
            expires_at__lte=timezone.now()
        ).count()
        
        self.stdout.write(f'Total magic users: {total_users}')
        self.stdout.write(f'Webhooks sent: {webhook_sent}')
        self.stdout.write(f'Webhooks pending: {webhook_pending}')
        self.stdout.write(f'Expired users: {expired_users}')
        
        # Recent webhook sent users
        self.stdout.write('\n=== RECENT WEBHOOK SENT USERS ===')
        recent_webhooks = MagicUser.objects.filter(
            webhook_sent=True,
            webhook_sent_at__isnull=False
        ).order_by('-webhook_sent_at')[:5]
        
        for user in recent_webhooks:
            self.stdout.write(
                f'- {user.email} - {user.webhook_sent_at.strftime("%Y-%m-%d %H:%M:%S")}'
            )

    def test_webhook_connection(self):
        """
        Test N8N webhook connection
        """
        webhook_url = self.get_webhook_url()
        if not webhook_url:
            return
        
        self.stdout.write(f'🔍 Testing N8N webhook connection: {webhook_url}')
        
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
                self.stdout.write(
                    self.style.SUCCESS('✅ N8N webhook connection successful!')
                )
                self.stdout.write(f'   Response: {response.text[:100]}')
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ N8N webhook error: HTTP {response.status_code}')
                )
                self.stdout.write(f'   Response: {response.text[:200]}')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Connection error: {str(e)}')
            )