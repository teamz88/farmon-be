from django.core.management.base import BaseCommand
from django.conf import settings
from apps.core.notifications import notification_service
import requests


class Command(BaseCommand):
    help = 'Test NTFY notification system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-connection',
            action='store_true',
            help='Test NTFY server connection',
        )
        parser.add_argument(
            '--test-notification',
            action='store_true',
            help='Test sending a notification',
        )
        parser.add_argument(
            '--test-question',
            action='store_true',
            help='Test sending a question notification',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing NTFY Notification System'))
        self.stdout.write(f'NTFY Server URL: {settings.NTFY_SERVER_URL}')
        self.stdout.write(f'NTFY Default Topic: {settings.NTFY_DEFAULT_TOPIC}')
        self.stdout.write(f'NTFY Default Email: {settings.NTFY_DEFAULT_EMAIL}')
        self.stdout.write('=' * 50)

        if options['test_connection']:
            self.test_connection()

        if options['test_notification']:
            self.test_notification()

        if options['test_question']:
            self.test_question_notification()

        if not any([options['test_connection'], options['test_notification'], options['test_question']]):
            # Run all tests by default
            self.test_connection()
            self.test_notification()
            self.test_question_notification()

    def test_connection(self):
        self.stdout.write('\nTesting NTFY server connection...')
        try:
            response = requests.get(f"{settings.NTFY_SERVER_URL}/v1/health", timeout=10)
            if response.status_code == 200:
                self.stdout.write(self.style.SUCCESS('✅ NTFY server is reachable'))
            else:
                self.stdout.write(self.style.ERROR(f'❌ NTFY server returned status: {response.status_code}'))
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f'❌ NTFY server connection failed: {str(e)}'))

    def test_notification(self):
        self.stdout.write('\nTesting basic notification...')
        try:
            result = notification_service.send_notification(
                message="Test notification from Django management command",
                title="Test Notification",
                priority=3
            )
            if result:
                self.stdout.write(self.style.SUCCESS('✅ Basic notification sent successfully'))
            else:
                self.stdout.write(self.style.ERROR('❌ Basic notification failed'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Basic notification error: {str(e)}'))

    def test_question_notification(self):
        self.stdout.write('\nTesting question notification...')
        try:
            result = notification_service.send_question_notification(
                user_email="test@example.com",
                question="This is a test question from Django management command",
                user_id=123
            )
            if result:
                self.stdout.write(self.style.SUCCESS('✅ Question notification sent successfully'))
            else:
                self.stdout.write(self.style.ERROR('❌ Question notification failed'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Question notification error: {str(e)}'))

        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS('Notification test completed!'))