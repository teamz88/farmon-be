from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import login
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import requests
import logging

from .models import User, UserSession, ClientInfo, MagicUser, PasswordReset
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
    UserSessionSerializer,
    ClientInfoSerializer,
    MagicUserRegistrationSerializer,
    MagicUserSerializer,
    MagicUserPasswordSetSerializer,
    UserListSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
)
from .permissions import IsAdminUser


class UserRegistrationView(generics.CreateAPIView):
    """User registration endpoint."""
    
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'User registered successfully',
            'user': UserProfileSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class UserLoginView(APIView):
    """User login endpoint with JWT token generation."""
    
    permission_classes = [permissions.AllowAny]
    
    def get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def post(self, request):
        serializer = UserLoginSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        logger.info(f'User login: {user.username}, password hash: {user.password[:50]}...')
        login(request, user)
        
        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        # Create user session
        session = UserSession.objects.create(
            user=user,
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'Login successful',
            'user': UserProfileSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'session_id': session.id
        }, status=status.HTTP_200_OK)


class ForgotPasswordView(APIView):
    """Handle forgot password requests."""
    
    permission_classes = [permissions.AllowAny]
    
    def get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            ip_address = self.get_client_ip(request)
            
            # Check rate limiting
            if not PasswordReset.can_request_reset(email, ip_address):
                return Response({
                    'error': 'Rate limit exceeded. You can only request password reset 3 times per day.'
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            # Create password reset request
            reset_request = PasswordReset.objects.create(
                email=email,
                ip_address=ip_address
            )
            
            # Send webhook to n8n
            self.send_reset_webhook(reset_request)
            
            return Response({
                'message': 'Password reset link has been sent to your email.'
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def send_reset_webhook(self, reset_request):
        """Send password reset webhook to n8n."""
        try:
            webhook_url = getattr(settings, 'N8N_RESET_PASSWORD_WEBHOOK_URL', None)
            if not webhook_url:
                logger.warning('N8N_RESET_PASSWORD_WEBHOOK_URL not configured in settings')
                return
            
            webhook_data = {
                'email': reset_request.email,
                'token': reset_request.token,
                'reset_link': f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')}/reset-password/{reset_request.token}",
                'created_at': reset_request.created_at.isoformat(),
            }
            
            response = requests.post(
                webhook_url,
                json=webhook_data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f'Password reset webhook sent successfully for {reset_request.email}')
            else:
                logger.error(f'Password reset webhook failed with status {response.status_code} for {reset_request.email}')
                
        except Exception as e:
            logger.error(f'Error sending password reset webhook for {reset_request.email}: {str(e)}')


class ResetPasswordView(APIView):
    """Handle password reset with token."""
    
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """Validate reset token."""
        token = request.query_params.get('token')
        if not token:
            return Response({
                'error': 'Token is required.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            reset_request = PasswordReset.objects.get(token=token, is_used=False)
            
            if reset_request.is_expired():
                return Response({
                    'error': 'Reset token has expired.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'message': 'Token is valid.',
                'email': reset_request.email
            }, status=status.HTTP_200_OK)
            
        except PasswordReset.DoesNotExist:
            return Response({
                'error': 'Invalid reset token.'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            token = serializer.validated_data['token']
            new_password = serializer.validated_data['new_password']
            
            try:
                # Get the reset request
                reset_request = PasswordReset.objects.get(token=token, is_used=False)
                
                if reset_request.is_expired():
                    return Response({
                        'error': 'Reset token has expired.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Get the user and update password
                user = User.objects.get(email=reset_request.email)
                user.set_password(new_password)
                user.save()
                
                # Mark reset request as used
                reset_request.is_used = True
                reset_request.save()
                
                return Response({
                    'message': 'Password has been reset successfully.'
                }, status=status.HTTP_200_OK)
                
            except PasswordReset.DoesNotExist:
                return Response({
                    'error': 'Invalid or expired reset token.'
                }, status=status.HTTP_400_BAD_REQUEST)
            except User.DoesNotExist:
                return Response({
                    'error': 'User not found.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Magic Link Views
logger = logging.getLogger(__name__)


class MagicLinkRegistrationView(generics.CreateAPIView):
    """Create magic link registration."""
    
    queryset = MagicUser.objects.all()
    serializer_class = MagicUserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Create magic user
            magic_user = serializer.save()
            
            # Check if user already exists with this email
            existing_user = User.objects.filter(email=magic_user.email).first()
            
            if existing_user:
                # Link existing user to magic user
                user = existing_user
                magic_user.created_user = user
                magic_user.is_account_created = True
                magic_user.save()
            else:
                # Automatically create user account and sign in
                user = magic_user.create_user_account(magic_user.generated_password)
                magic_user.is_account_created = True
                magic_user.save()
            
            # Generate JWT tokens for automatic sign in
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token
            
            # Create user session
            session = UserSession.objects.create(
                user=user,
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Send webhook to n8n
            self.send_webhook(magic_user)
            
            return Response({
                'message': 'Account created and signed in successfully',
                'magic_link': magic_user.magic_link,
                'access': str(access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                },
                'session_id': session.id
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f'Error in magic link registration: {str(e)}')
            
            # Handle specific database constraint errors
            if 'duplicate key value violates unique constraint' in str(e):
                if 'username' in str(e):
                    return Response({
                        'error': 'Username already exists. Please try again.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                elif 'email' in str(e):
                    return Response({
                        'error': 'Email already exists. Please try again.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'error': 'Failed to create magic link registration'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def send_webhook(self, magic_user):
        """Send webhook to n8n with magic user data."""
        try:
            webhook_url = getattr(settings, 'N8N_WEBHOOK_URL', None)
            if not webhook_url:
                logger.warning('N8N_WEBHOOK_URL not configured in settings')
                return
            
            webhook_data = {
                'magic_link': magic_user.magic_link,
                'first_name': magic_user.first_name,
                'last_name': magic_user.last_name,
                'email': magic_user.email,
                'company_name': magic_user.company_name,
                'phone_number': magic_user.phone_number,
                'created_at': magic_user.created_at.isoformat(),
            }
            
            response = requests.post(
                webhook_url,
                json=webhook_data,
                timeout=10
            )
            
            if response.status_code == 200:
                magic_user.webhook_sent = True
                magic_user.save(update_fields=['webhook_sent'])
                logger.info(f'Webhook sent successfully for magic user {magic_user.id}')
            else:
                logger.error(f'Webhook failed with status {response.status_code} for magic user {magic_user.id}')
                
        except Exception as e:
            logger.error(f'Error sending webhook for magic user {magic_user.id}: {str(e)}')


class MagicLinkValidationView(APIView):
    """Validate magic link and return user data."""
    
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, token):
        try:
            magic_user = MagicUser.objects.get(magic_token=token)
            
            if magic_user.is_expired():
                return Response({
                    'error': 'Magic link has expired'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if magic_user.is_used:
                return Response({
                    'error': 'Magic link has already been used'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = MagicUserSerializer(magic_user)
            return Response({
                'valid': True,
                'user_data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except MagicUser.DoesNotExist:
            return Response({
                'error': 'Invalid magic link'
            }, status=status.HTTP_404_NOT_FOUND)


class MagicLinkPasswordSetView(APIView):
    """Set password for magic link user and create account."""
    
    permission_classes = [permissions.AllowAny]
    
    def get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def post(self, request, token):
        try:
            magic_user = MagicUser.objects.get(magic_token=token)
            
            if magic_user.is_expired():
                return Response({
                    'error': 'Magic link has expired'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if magic_user.is_used:
                return Response({
                    'error': 'Magic link has already been used'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = MagicUserPasswordSetSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Create or update user account
            password = serializer.validated_data['password']
            logger.info(f'Setting password for magic user {magic_user.email}')
            
            if magic_user.is_account_created and magic_user.created_user:
                # Update existing user's password
                user = magic_user.created_user
                user.set_password(password)
                user.save()
                logger.info(f'Updated existing user: {user.username}, password hash: {user.password[:50]}...')
            else:
                # Create new user account
                user = magic_user.create_user_account(password)
                logger.info(f'User created: {user.username}, password hash: {user.password[:50]}...')
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token
            
            # Create user session
            session = UserSession.objects.create(
                user=user,
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Mark magic user as used
            magic_user.is_used = True
            magic_user.is_account_created = True
            magic_user.save(update_fields=['is_used', 'is_account_created'])
            
            return Response({
                'message': 'Account created successfully',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                },
                'tokens': {
                    'access': str(access_token),
                    'refresh': str(refresh),
                }
            }, status=status.HTTP_201_CREATED)
            
        except MagicUser.DoesNotExist:
            return Response({
                'error': 'Invalid magic link'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f'Error creating account from magic link: {str(e)}')
            
            # Handle specific database constraint errors
            if 'duplicate key value violates unique constraint' in str(e):
                if 'username' in str(e):
                    return Response({
                        'error': 'Username already exists. Please try again.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                elif 'email' in str(e):
                    return Response({
                        'error': 'Email already exists. Please try again.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'error': 'Failed to create account'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ClientInfoView(generics.RetrieveUpdateAPIView):
    """Client information view and update endpoint."""
    
    serializer_class = ClientInfoSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        """Get or create client info for the current user."""
        client_info, created = ClientInfo.objects.get_or_create(
            user=self.request.user
        )
        return client_info
    
    def perform_update(self, serializer):
        """Mark client info as completed when updated."""
        serializer.save(is_completed=True)


class AdminClientInfoView(generics.RetrieveAPIView):
    """Admin-only endpoint to view client info for any user."""
    
    serializer_class = ClientInfoSerializer
    permission_classes = [IsAdminUser]
    
    def get_object(self):
        """Get client info for the specified user."""
        user_id = self.kwargs['user_id']
        try:
            user = User.objects.get(id=user_id)
            client_info = ClientInfo.objects.get(user=user)
            return client_info
        except (User.DoesNotExist, ClientInfo.DoesNotExist):
            return None
    
    def retrieve(self, request, *args, **kwargs):
        """Return client info or null if not found."""
        instance = self.get_object()
        if instance is None:
            return Response(None, status=status.HTTP_200_OK)
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def check_client_info_status(request):
    """Check if user has completed client info form."""
    try:
        client_info = ClientInfo.objects.get(user=request.user)
        return Response({
            'has_client_info': True,
            'is_completed': client_info.is_completed
        }, status=status.HTTP_200_OK)
    except ClientInfo.DoesNotExist:
        return Response({
            'has_client_info': False,
            'is_completed': False
        }, status=status.HTTP_200_OK)


class UserLogoutView(APIView):
    """User logout endpoint."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            # End current session if session_id provided
            session_id = request.data.get('session_id')
            if session_id:
                try:
                    session = UserSession.objects.get(
                        id=session_id,
                        user=request.user,
                        session_end__isnull=True
                    )
                    session.end_session()
                except UserSession.DoesNotExist:
                    pass
            
            # Blacklist refresh token if provided
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            return Response({
                'message': 'Logout successful'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': 'Logout failed',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """User profile view and update endpoint."""
    
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    """Change user password endpoint."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'message': 'Password changed successfully'
        }, status=status.HTTP_200_OK)


class UserListView(generics.ListAPIView):
    """Admin-only endpoint to list all users."""
    
    queryset = User.objects.all()
    serializer_class = UserListSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by role
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        
        # Filter by subscription status
        subscription_status = self.request.query_params.get('subscription_status')
        if subscription_status:
            queryset = queryset.filter(subscription_status=subscription_status)
        
        # Filter by subscription type
        subscription_type = self.request.query_params.get('subscription_type')
        if subscription_type:
            queryset = queryset.filter(subscription_type=subscription_type)
        
        # Search by username, email, or name
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )
        
        # Order by
        ordering = self.request.query_params.get('ordering', '-date_joined')
        if ordering:
            queryset = queryset.order_by(ordering)
        
        return queryset


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin-only endpoint to view, update, or delete specific users."""
    
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAdminUser]
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return UserListSerializer
        return UserProfileSerializer
    
    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user.is_admin:
            return Response({
                'error': 'Cannot delete admin users'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return super().destroy(request, *args, **kwargs)


class UserSessionListView(generics.ListAPIView):
    """List user sessions (admin can see all, users see their own)."""
    
    serializer_class = UserSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_admin:
            queryset = UserSession.objects.all()
            
            # Filter by user
            user_id = self.request.query_params.get('user_id')
            if user_id:
                queryset = queryset.filter(user_id=user_id)
        else:
            queryset = UserSession.objects.filter(user=self.request.user)
        
        return queryset.order_by('-session_start')


@api_view(['POST'])
@permission_classes([IsAdminUser])
def upgrade_user_subscription(request, user_id):
    """Admin endpoint to upgrade user subscription."""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    subscription_type = request.data.get('subscription_type')
    duration_days = request.data.get('duration_days')
    
    if not subscription_type:
        return Response({
            'error': 'subscription_type is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if subscription_type not in [choice[0] for choice in User.SubscriptionType.choices]:
        return Response({
            'error': 'Invalid subscription type'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user.upgrade_subscription(subscription_type, duration_days)
        return Response({
            'message': 'Subscription upgraded successfully',
            'user': UserProfileSerializer(user).data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': 'Failed to upgrade subscription',
            'detail': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_stats(request):
    """Get current user's statistics."""
    user = request.user
    
    # Get user's sessions
    sessions = user.sessions.all()
    total_sessions = sessions.count()
    active_sessions = sessions.filter(session_end__isnull=True).count()
    
    # Calculate average session duration
    completed_sessions = sessions.filter(session_end__isnull=False)
    if completed_sessions.exists():
        total_duration = sum(
            (session.session_end - session.session_start).total_seconds()
            for session in completed_sessions
        )
        avg_session_duration = total_duration / completed_sessions.count()
    else:
        avg_session_duration = 0
    
    return Response({
        'total_sessions': total_sessions,
        'active_sessions': active_sessions,
        'avg_session_duration_seconds': avg_session_duration,
        'total_time_spent_seconds': user.total_time_spent.total_seconds(),
        'total_files': user.files.count(),
        'total_chat_messages': user.chat_messages.count(),
        'subscription_info': {
            'type': user.subscription_type,
            'status': user.subscription_status,
            'is_active': user.is_subscription_active,
            'days_until_expiry': user.days_until_expiry,
            'start_date': user.subscription_start_date,
            'end_date': user.subscription_end_date,
        }
    }, status=status.HTTP_200_OK)