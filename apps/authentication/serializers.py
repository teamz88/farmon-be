from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, UserSession, ClientInfo, MagicUser


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = (
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'phone_number'
        )
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
        }
    
    def validate_email(self, value):
        """Validate email uniqueness."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def validate_username(self, value):
        """Validate username uniqueness."""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value
    
    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Password confirmation doesn't match.")
        return attrs
    
    def create(self, validated_data):
        """Create new user."""
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    
    username = serializers.CharField()
    password = serializers.CharField(style={'input_type': 'password'})
    
    def validate(self, attrs):
        """Validate user credentials."""
        import logging
        logger = logging.getLogger(__name__)
        
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            logger.info(f'Login attempt for: {username}')
            # Try to authenticate with username or email
            user = authenticate(
                request=self.context.get('request'),
                username=username,
                password=password
            )
            logger.info(f'Username auth result: {bool(user)}')
            
            if not user:
                # Try with email if username authentication failed
                try:
                    user_obj = User.objects.get(email=username)
                    logger.info(f'Found user by email: {user_obj.username}, password hash: {user_obj.password[:50]}...')
                    user = authenticate(
                        request=self.context.get('request'),
                        username=user_obj.username,
                        password=password
                    )
                    logger.info(f'Email auth result: {bool(user)}')
                except User.DoesNotExist:
                    logger.info(f'No user found with email: {username}')
                    pass
            
            if not user:
                raise serializers.ValidationError('Invalid credentials.')
            
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled.')
            
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError('Must include username and password.')


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile information."""
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    is_subscription_active = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'full_name', 'phone_number', 'avatar', 'role',
            'subscription_type', 'subscription_status',
            'subscription_start_date', 'subscription_end_date',
            'is_subscription_active', 'days_until_expiry',
            'email_notifications', 'last_activity', 'total_time_spent',
            'date_joined', 'last_login'
        )
        read_only_fields = (
            'id', 'username', 'role', 'subscription_type',
            'subscription_status', 'subscription_start_date',
            'subscription_end_date', 'last_activity', 'total_time_spent',
            'date_joined', 'last_login'
        )
    
    def validate_email(self, value):
        """Validate email uniqueness (excluding current user)."""
        user = self.instance
        if user and User.objects.filter(email=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value


class UserListSerializer(serializers.ModelSerializer):
    """Serializer for user list (admin view)."""
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    is_subscription_active = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    total_files = serializers.SerializerMethodField()
    total_chat_messages = serializers.SerializerMethodField()
    total_payments = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'full_name', 'role',
            'subscription_type', 'subscription_status',
            'subscription_start_date', 'subscription_end_date',
            'is_subscription_active', 'days_until_expiry',
            'total_time_spent', 'last_activity', 'date_joined',
            'total_files', 'total_chat_messages', 'total_payments',
            'is_active'
        )
    
    def get_total_files(self, obj):
        """Get total number of files uploaded by user."""
        return obj.files.count()
    
    def get_total_chat_messages(self, obj):
        """Get total number of chat messages sent by user."""
        return obj.chat_messages.count()
    
    def get_total_payments(self, obj):
        """Get total number of payments made by user."""
        return obj.payments.count()


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing user password."""
    
    old_password = serializers.CharField(style={'input_type': 'password'})
    new_password = serializers.CharField(
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(style={'input_type': 'password'})
    
    def validate_old_password(self, value):
        """Validate old password."""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value
    
    def validate(self, attrs):
        """Validate new password confirmation."""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New password confirmation doesn't match.")
        return attrs
    
    def save(self):
        """Save new password."""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class UserSessionSerializer(serializers.ModelSerializer):
    """Serializer for user session information."""
    
    duration = serializers.DurationField(read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = UserSession
        fields = (
            'id', 'user_username', 'session_start', 'session_end',
            'duration', 'ip_address', 'user_agent',
            'pages_visited', 'chat_messages_sent', 'files_uploaded'
        )
        read_only_fields = ('id', 'session_start')


class ClientInfoSerializer(serializers.ModelSerializer):
    """Serializer for client business information."""
    
    class Meta:
        model = ClientInfo
        fields = (
            'id', 'company_name', 'owner_name', 'state', 'city',
            'year_started', 'trucks_count', 'monthly_revenue',
            'gross_profit_margin', 'main_services', 'pricing_model',
            'software_tools', 'current_challenges', 'is_completed',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
    
    def validate_year_started(self, value):
        """Validate year started is reasonable."""
        if value and (value < 1900 or value > 2024):
            raise serializers.ValidationError("Please enter a valid year.")
        return value
    
    def validate_gross_profit_margin(self, value):
        """Validate gross profit margin is between 0 and 100."""
        if value and (value < 0 or value > 100):
            raise serializers.ValidationError("Gross profit margin must be between 0 and 100 percent.")
        return value


class MagicUserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for magic link user registration."""
    
    class Meta:
        model = MagicUser
        fields = (
            'first_name', 'last_name', 'email', 'company_name', 'phone_number'
        )
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'email': {'required': True},
        }
    
    def validate_email(self, value):
        """Validate email uniqueness across both User and MagicUser models."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        if MagicUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("A magic link has already been sent to this email.")
        return value
    
    def create(self, validated_data):
        """Create MagicUser with all required fields."""
        from django.utils import timezone
        from datetime import timedelta
        from django.conf import settings
        
        # Generate required fields
        magic_token = MagicUser.generate_magic_token()
        generated_username = MagicUser.generate_username(
            validated_data['first_name'], 
            validated_data['email']
        )
        generated_password = MagicUser.generate_password()
        
        # Set expiration time (7 days from now)
        expires_at = timezone.now() + timedelta(days=7)
        
        # Generate magic link URL
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        magic_link = f"{frontend_url}/magic-link/set-password?token={magic_token}"
        
        # Create the MagicUser instance
        magic_user = MagicUser.objects.create(
            magic_token=magic_token,
            magic_link=magic_link,
            generated_username=generated_username,
            generated_password=generated_password,
            expires_at=expires_at,
            **validated_data
        )
        
        return magic_user


class MagicUserSerializer(serializers.ModelSerializer):
    """Serializer for MagicUser model."""
    
    class Meta:
        model = MagicUser
        fields = (
            'id', 'first_name', 'last_name', 'email', 'company_name',
            'phone_number', 'magic_link', 'generated_username',
            'is_used', 'is_account_created', 'webhook_sent',
            'created_at', 'expires_at'
        )
        read_only_fields = (
            'id', 'magic_link', 'generated_username', 'is_used',
            'is_account_created', 'webhook_sent', 'created_at', 'expires_at'
        )


class MagicUserPasswordSetSerializer(serializers.Serializer):
    """Serializer for setting password for magic link users."""
    
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Password confirmation doesn't match.")
        return attrs