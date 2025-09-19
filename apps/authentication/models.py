from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta
import uuid
import secrets
import string


class User(AbstractUser):
    """Custom User model with additional fields for subscription and profile management."""
    
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        USER = 'user', 'User'

    class SubscriptionType(models.TextChoices):
        FREE = 'free', 'Free'
        BASIC = 'basic', 'Basic'
        PREMIUM = 'premium', 'Premium'
        LIFETIME = 'lifetime', 'Lifetime'

    class SubscriptionStatus(models.TextChoices):
        ACTIVE = 'active', 'Active'
        EXPIRED = 'expired', 'Expired'
        CANCELLED = 'cancelled', 'Cancelled'
        PENDING = 'pending', 'Pending'

    # User role and permissions
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.USER,
        help_text="User role determining access permissions"
    )

    # Subscription fields
    subscription_type = models.CharField(
        max_length=10,
        choices=SubscriptionType.choices,
        default=SubscriptionType.FREE,
        help_text="Type of subscription"
    )

    subscription_status = models.CharField(
        max_length=10,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
        help_text="Current subscription status"
    )

    subscription_start_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the current subscription started"
    )

    subscription_end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the current subscription expires"
    )

    # Profile fields
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="User's phone number"
    )
    
    title = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="User's job title"
    )
    
    position = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="User's position in company"
    )

    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        help_text="User's profile picture"
    )

    # Activity tracking
    last_activity = models.DateTimeField(
        auto_now=True,
        help_text="Last time user was active"
    )

    total_time_spent = models.DurationField(
        default=timedelta(0),
        help_text="Total time spent in the application"
    )

    # Token usage tracking
    total_tokens_used = models.PositiveIntegerField(
        default=0,
        help_text="Total number of tokens used by the user"
    )

    input_tokens_used = models.PositiveIntegerField(
        default=0,
        help_text="Total input tokens used by the user"
    )

    output_tokens_used = models.PositiveIntegerField(
        default=0,
        help_text="Total output tokens used by the user"
    )

    last_token_usage_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time user used tokens"
    )

    # Preferences
    email_notifications = models.BooleanField(
        default=True,
        help_text="Whether user wants to receive email notifications"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'auth_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.username} ({self.get_full_name()})"

    @property
    def is_admin(self):
        """Check if user is an admin."""
        return self.role == self.Role.ADMIN

    @property
    def is_subscription_active(self):
        """Check if user's subscription is currently active."""
        if self.subscription_status != self.SubscriptionStatus.ACTIVE:
            return False
        
        if self.subscription_type == self.SubscriptionType.LIFETIME:
            return True
        
        if self.subscription_end_date:
            return timezone.now() <= self.subscription_end_date
        
        # If no end date is set, consider it active
        return True

    @property
    def days_until_expiry(self):
        """Get number of days until subscription expires."""
        if self.subscription_type == self.SubscriptionType.LIFETIME:
            return None
        
        if self.subscription_end_date:
            delta = self.subscription_end_date - timezone.now()
            return max(0, delta.days)
        
        return None

    def extend_subscription(self, days):
        """Extend subscription by specified number of days."""
        if self.subscription_end_date:
            self.subscription_end_date += timedelta(days=days)
        else:
            self.subscription_end_date = timezone.now() + timedelta(days=days)
        
        self.subscription_status = self.SubscriptionStatus.ACTIVE
        self.save(update_fields=['subscription_end_date', 'subscription_status'])

    def upgrade_subscription(self, new_type, duration_days=None):
        """Upgrade user's subscription to a new type."""
        self.subscription_type = new_type
        self.subscription_status = self.SubscriptionStatus.ACTIVE
        
        if new_type == self.SubscriptionType.LIFETIME:
            self.subscription_end_date = None
        elif duration_days:
            self.subscription_start_date = timezone.now()
            self.subscription_end_date = timezone.now() + timedelta(days=duration_days)
        
        self.save(update_fields=[
            'subscription_type', 
            'subscription_status', 
            'subscription_start_date', 
            'subscription_end_date'
        ])

    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f'{self.first_name} {self.last_name}'
        return full_name.strip()


class ClientInfo(models.Model):
    """Client business information model for storing detailed business data."""
    
    PRICING_MODEL_CHOICES = [
        ('by_weight', 'By weight'),
        ('by_volume', 'By volume'),
        ('by_hour', 'By the hour'),
        ('other', 'Other'),
    ]
    
    REVENUE_RANGE_CHOICES = [
        ('0-250k', '$0 - $250,000'),
        ('250k-500k', '$250,000 - $500,000'),
        ('500k-1m', '$500,000 - $1,000,000'),
        ('1m-2m', '$1,000,000 - $2,000,000'),
        ('2m-4m', '$2,000,000 - $4,000,000'),
        ('4m+', '$4,000,000+'),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='client_info',
        help_text="Associated user account"
    )
    
    # Basic company information
    company_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Company name"
    )
    
    owner_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Owner/Your name"
    )
    
    # Location
    state = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="State/Province"
    )
    
    city = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="City"
    )
    
    # Business details
    year_started = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Year business was started"
    )
    
    trucks_count = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Number of trucks in operation"
    )
    
    monthly_revenue = models.CharField(
        max_length=20,
        choices=REVENUE_RANGE_CHOICES,
        blank=True,
        null=True,
        help_text="Monthly revenue range"
    )
    
    gross_profit_margin = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Gross profit margin estimate (percentage)"
    )
    
    # Services and tools
    main_services = models.JSONField(
        default=list,
        blank=True,
        help_text="Main services offered (checklist)"
    )
    
    pricing_model = models.CharField(
        max_length=20,
        choices=PRICING_MODEL_CHOICES,
        blank=True,
        null=True,
        help_text="Pricing model used"
    )
    
    # Software and challenges
    software_tools = models.JSONField(
        default=list,
        blank=True,
        help_text="Software tools used (CRM, booking, GPS, etc.)"
    )
    
    # Challenges and completion status
    current_challenges = models.TextField(
        blank=True,
        null=True,
        help_text="Top current challenges (free text)"
    )
    
    # Completion tracking
    is_completed = models.BooleanField(
        default=False,
        help_text="Whether the client info form has been completed"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'client_info'
        verbose_name = 'Client Info'
        verbose_name_plural = 'Client Info'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Client Info for {self.user.username} - {self.company_name or 'No Company'}"


class UserSession(models.Model):
    """Model to track user sessions and activity."""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    
    session_start = models.DateTimeField(auto_now_add=True)
    session_end = models.DateTimeField(null=True, blank=True)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Activity metrics
    pages_visited = models.PositiveIntegerField(default=0)
    chat_messages_sent = models.PositiveIntegerField(default=0)
    files_uploaded = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'user_sessions'
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
        ordering = ['-session_start']
    
    def __str__(self):
        return f"{self.user.username} - {self.session_start.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def duration(self):
        """Calculate session duration."""
        if self.session_end:
            return self.session_end - self.session_start
        return timezone.now() - self.session_start
    
    def end_session(self):
        """End the current session and update user's total time spent."""
        if not self.session_end:
            self.session_end = timezone.now()
            self.save(update_fields=['session_end'])
            
            # Update user's total time spent
            self.user.total_time_spent += self.duration
            self.user.save(update_fields=['total_time_spent'])


class MagicUser(models.Model):
    """Model to store magic link user registrations before account creation."""
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Required fields
    first_name = models.CharField(
        max_length=150,
        help_text="User's first name"
    )
    
    last_name = models.CharField(
        max_length=150,
        help_text="User's last name"
    )
    
    email = models.EmailField(
        unique=True,
        help_text="User's email address"
    )
    
    # Optional fields
    company_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Company name"
    )
    
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="User's phone number"
    )
    
    title = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="User's job title"
    )
    
    position = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="User's position in company"
    )

    # Magic link fields
    magic_token = models.CharField(
        max_length=64,
        unique=True,
        help_text="Unique token for magic link"
    )
    
    magic_link = models.URLField(
        help_text="Generated magic link URL"
    )
    
    # Generated credentials
    generated_username = models.CharField(
        max_length=150,
        unique=True,
        help_text="Auto-generated username"
    )
    
    generated_password = models.CharField(
        max_length=128,
        help_text="Auto-generated temporary password"
    )
    
    # Status tracking
    is_used = models.BooleanField(
        default=False,
        help_text="Whether the magic link has been used"
    )
    
    is_account_created = models.BooleanField(
        default=False,
        help_text="Whether the user account has been created"
    )
    
    created_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='magic_registrations',
        help_text="The created user account (if any)"
    )
    
    # Webhook tracking
    webhook_sent = models.BooleanField(
        default=False,
        help_text="Whether webhook has been sent to n8n"
    )
    
    webhook_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When webhook was sent"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(
        help_text="When the magic link expires"
    )
    
    class Meta:
        db_table = 'magic_users'
        verbose_name = 'Magic User'
        verbose_name_plural = 'Magic Users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    @classmethod
    def generate_magic_token(cls):
        """Generate a secure random token for magic link."""
        return secrets.token_urlsafe(32)
    
    @classmethod
    def generate_username(cls, first_name, email):
        """Generate unique username from first name and email."""
        # Create base username from first name and email prefix
        email_prefix = email.split('@')[0]
        base_username = f"{first_name.lower()}.{email_prefix.lower()}"
        
        # Remove special characters and limit length
        base_username = ''.join(c for c in base_username if c.isalnum() or c in '._')
        base_username = base_username[:30]  # Limit to 30 chars
        
        # Ensure uniqueness
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists() or cls.objects.filter(generated_username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
            if len(username) > 30:
                # If too long, truncate base and try again
                base_username = base_username[:25]
                username = f"{base_username}{counter}"
        
        return username
    
    @classmethod
    def generate_password(cls):
        """Generate a secure random password."""
        # Generate a 12-character password with letters, digits, and special characters
        characters = string.ascii_letters + string.digits + '!@#$%^&*'
        return ''.join(secrets.choice(characters) for _ in range(12))
    
    def create_user_account(self, password):
        """Create a User account from MagicUser data."""
        user = User.objects.create_user(
            username=self.generated_username,
            email=self.email,
            password=password,
            first_name=self.first_name,
            last_name=self.last_name
        )
        
        # Set additional fields
        user.phone_number = self.phone_number
        user.title = self.title
        user.position = self.position
        user.save()
        
        # Link the created user to this magic user
        self.created_user = user
        self.save(update_fields=['created_user'])
        
        return user
    
    def is_expired(self):
        """Check if the magic link has expired."""
        return timezone.now() > self.expires_at


class PasswordReset(models.Model):
    """Model for handling password reset requests."""
    
    email = models.EmailField(
        help_text="Email address for password reset"
    )
    
    token = models.CharField(
        max_length=64,
        unique=True,
        help_text="Unique token for password reset"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the reset request was created"
    )
    
    expires_at = models.DateTimeField(
        help_text="When the reset token expires"
    )
    
    is_used = models.BooleanField(
        default=False,
        help_text="Whether the reset token has been used"
    )
    
    # Rate limiting fields
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the request"
    )
    
    class Meta:
        db_table = 'password_resets'
        verbose_name = 'Password Reset'
        verbose_name_plural = 'Password Resets'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'created_at']),
            models.Index(fields=['token']),
        ]
    
    def __str__(self):
        return f"Password reset for {self.email}"
    
    @classmethod
    def generate_token(cls):
        """Generate a secure random token."""
        return secrets.token_urlsafe(32)
    
    def is_expired(self):
        """Check if the reset token has expired."""
        return timezone.now() > self.expires_at
    
    @classmethod
    def can_request_reset(cls, email, ip_address=None):
        """Check if user can request password reset (rate limiting)."""
        # Check requests in last 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        
        # Count requests by email
        email_requests = cls.objects.filter(
            email=email,
            created_at__gte=yesterday
        ).count()
        
        # Count requests by IP (if provided)
        ip_requests = 0
        if ip_address:
            ip_requests = cls.objects.filter(
                ip_address=ip_address,
                created_at__gte=yesterday
            ).count()
        
        # Allow max 3 requests per email or IP per day
        return email_requests < 3 and ip_requests < 3

    def save(self, *args, **kwargs):
        """Override save to generate token and expiration if not set."""
        if not self.token:
            self.token = self.generate_token()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)