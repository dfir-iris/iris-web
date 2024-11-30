from typing import Optional
from flask_login import current_user
import werkzeug.exceptions


class UnauthorizedException(werkzeug.exceptions.Forbidden):
    """`UnauthorizedException` will be raised when an access control check fails.
    
    Args:
        resource (str): The resource type
        action (str): The type of action performed
        resource_id (str, optional): The resource ID that was the action attempt was for
        
    Returns:
        `UnauthorizedException` with args:
            0, user_id, optional
            1, resource
            2, action
            3, resource_id, optional
    """
    
    def __init__(self, resource, action, resource_id: Optional[str] = None) -> None:
        # Get current user ID
        user_id = current_user.id if current_user.is_authenticated else None
        
        # Set exception args
        self.args = (user_id, resource, action, resource_id)
        
        super().__init__()
    