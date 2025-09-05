from django.core.management.base import BaseCommand
from apps.authentication.models import MagicUser, User
from django.contrib.auth.hashers import check_password

class Command(BaseCommand):
    help = 'Test magic link password setting'
    
    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email of magic user')
        parser.add_argument('password', type=str, help='Password to test')
    
    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        
        try:
            # Find magic user
            magic_user = MagicUser.objects.get(email=email)
            self.stdout.write(f"Found magic user: {magic_user}")
            
            if magic_user.is_account_created and magic_user.created_user:
                user = magic_user.created_user
                self.stdout.write(f"User account exists: {user.username}")
                self.stdout.write(f"Password hash: {user.password[:50]}...")
                
                # Test password
                if check_password(password, user.password):
                    self.stdout.write(self.style.SUCCESS("Password matches!"))
                else:
                    self.stdout.write(self.style.ERROR("Password does not match!"))
                    
                    # Try to set password manually
                    user.set_password(password)
                    user.save()
                    self.stdout.write("Password reset manually")
                    
                    if check_password(password, user.password):
                        self.stdout.write(self.style.SUCCESS("Password now matches after manual reset!"))
            else:
                self.stdout.write("No user account created yet")
                
        except MagicUser.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Magic user with email {email} not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))