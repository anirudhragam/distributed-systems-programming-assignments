# Session management for seller CLI
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class SellerSession:
    """Represents an active seller session"""
    session_id: Optional[str] = None
    seller_id: Optional[int] = None
    seller_name: Optional[str] = None
    logged_in: bool = False
    login_time: Optional[datetime] = None
    
    def is_logged_in(self) -> bool:
        """Check if seller is currently logged in"""
        return self.logged_in and self.session_id is not None
    
    def clear(self):
        """Clear session data after logout"""
        self.session_id = None
        self.seller_id = None
        self.seller_name = None
        self.logged_in = False
        self.login_time = None
