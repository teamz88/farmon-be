from django.conf import settings
from ntfybro import NtfyNotifier
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service class for sending notifications via Ntfy.sh
    """
    
    def __init__(self):
        self.notifier = NtfyNotifier(
            server_url=settings.NTFY_SERVER_URL,
            default_topic=settings.NTFY_DEFAULT_TOPIC,
            default_email=settings.NTFY_DEFAULT_EMAIL
        )
    
    def send_notification(self, message, title=None, priority=3, tags=None, **kwargs):
        """
        General notification sending function
        """
        try:
            # Log the attempt
            logger.info(f"Attempting to send notification: {title} - {message[:100]}...")
            logger.debug(f"NTFY Config - Server: {settings.NTFY_SERVER_URL}, Topic: {settings.NTFY_DEFAULT_TOPIC}")
            
            result = self.notifier.send_notification(
                message=message,
                title=title,
                priority=priority,
                tags=tags,
                **kwargs
            )
            
            if result:
                logger.info(f"Notification sent successfully: {title} - {message[:50]}...")
            else:
                logger.error(f"Notification failed (returned False): {title} - {message[:50]}...")
                
            return result
            
        except Exception as e:
            logger.error(f"Exception sending notification: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def send_user_registration_notification(self, user_email, user_name=None):
        """
        Send notification when a new user registers
        """
        title = "New User Registration"
        message = f"New user registered: {user_email}"
        if user_name:
            message += f" ({user_name})"
        
        return self.send_notification(
            message=message,
            title=title,
            priority=3,
            tags="user,registration,new"
        )
    
    def send_password_reset_notification(self, user_email):
        """
        Send notification when password reset is requested
        """
        title = "Password Reset Request"
        message = f"Password reset requested for: {user_email}"
        
        return self.send_notification(
            message=message,
            title=title,
            priority=4,
            tags="password,reset,security"
        )
    
    def send_question_notification(self, user_email, question, user_id=None):
        """
        Send notification when a user asks a question
        """
        title = "New Question Asked"
        message = f"User asked a question: {user_email}"
        if question:
            message += f"\nQuestion: {question[:200]}{'...' if len(question) > 200 else ''}"
        
        if user_id:
            message += f"\nUser ID: {user_id}"
        
        return self.send_notification(
            message=message,
            title=title,
            priority=4,  # High priority
            tags="question,user,chat"
        )
    
    def send_error_notification(self, error_message, error_type="General Error", user_email=None):
        """
        Send notification when an error occurs
        """
        title = f"Error: {error_type}"
        message = f"System error occurred: {error_message}"
        if user_email:
            message += f"\nUser: {user_email}"
        
        return self.send_notification(
            message=message,
            title=title,
            priority=5,  # Highest priority
            tags="error,critical,system"
        )
    
    def send_success_notification(self, message, title="Success"):
        """
        Send notification for successful operations
        """
        return self.send_notification(
            message=message,
            title=title,
            priority=2,
            tags="success,info"
        )
    
    def send_warning_notification(self, message, title="Warning"):
        """
        Send notification for warnings
        """
        return self.send_notification(
            message=message,
            title=title,
            priority=4,
            tags="warning,alert"
        )
    
    def send_rag_api_call_notification(self, user_email, question, api_type="chat", user_id=None):
        """
        Send notification when RAG API is called
        """
        title = f"RAG API Call - {api_type.title()}"
        message = f"RAG API called by: {user_email}"
        if question:
            message += f"\nQuestion: {question[:200]}{'...' if len(question) > 200 else ''}"
        
        if user_id:
            message += f"\nUser ID: {user_id}"
        
        return self.send_notification(
            message=message,
            title=title,
            priority=3,
            tags="rag,api,call,chat"
        )
    
    def send_rag_feedback_notification(self, user_email, feedback_type, question, answer, user_id=None):
        """
        Send notification when feedback is submitted to RAG API
        """
        title = f"RAG Feedback - {feedback_type.title()}"
        message = f"Feedback submitted by: {user_email}\nType: {feedback_type}"
        if question:
            message += f"\nQuestion: {question[:150]}{'...' if len(question) > 150 else ''}"
        if answer:
            message += f"\nAnswer: {answer[:150]}{'...' if len(answer) > 150 else ''}"
        
        if user_id:
            message += f"\nUser ID: {user_id}"
        
        return self.send_notification(
            message=message,
            title=title,
            priority=3,
            tags="rag,feedback,api"
        )
    
    def send_rag_file_upload_notification(self, user_email, file_name, file_size=None, user_id=None):
        """
        Send notification when file is uploaded to RAG API
        """
        title = "RAG File Upload"
        message = f"File uploaded to RAG by: {user_email}\nFile: {file_name}"
        if file_size:
            message += f"\nSize: {file_size}"
        
        if user_id:
            message += f"\nUser ID: {user_id}"
        
        return self.send_notification(
            message=message,
            title=title,
            priority=3,
            tags="rag,file,upload,api"
        )
    
    def send_rag_api_error_notification(self, user_email, error_message, api_type="chat", question=None, user_id=None):
        """
        Send notification when RAG API encounters an error
        """
        title = f"RAG API Error - {api_type.title()}"
        message = f"RAG API error for user: {user_email}\nError: {error_message[:300]}{'...' if len(error_message) > 300 else ''}"
        
        if question:
            message += f"\nQuestion: {question[:150]}{'...' if len(question) > 150 else ''}"
        
        if user_id:
            message += f"\nUser ID: {user_id}"
        
        return self.send_notification(
            message=message,
            title=title,
            priority=5,  # High priority for errors
            tags="rag,api,error,alert"
        )

# Global notification service instance
notification_service = NotificationService()