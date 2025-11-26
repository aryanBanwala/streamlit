"""
Centralized client dependencies for the temporal workers application.
Provides singleton instances of database and external service clients.
"""

import os
import logging
from typing import Optional
from supabase import create_client, Client
from pinecone import Pinecone
from openai import OpenAI, AsyncOpenAI
import dotenv

# Load environment variables
dotenv.load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Global client instances
_supabase_client: Optional[Client] = None
_pinecone_client: Optional[Pinecone] = None
_openrouter_client: Optional[OpenAI] = None
_async_openrouter_client: Optional[AsyncOpenAI] = None


def get_supabase_client() -> Client:
    """
    Get or create a Supabase client instance.
    
    Returns:
        Client: Supabase client instance
        
    Raises:
        ValueError: If required environment variables are not set
    """
    global _supabase_client
    
    if _supabase_client is None:
        environment = os.getenv("ENVIRONMENT", "local").lower()
        if environment in ["preprod", "local"]:
            # Use pre-production credentials
            url_env_var = "SUPABASE_URL_PREPROD"
            key_env_var = "SUPABASE_SERVICE_ROLE_KEY_PREPROD"
        elif environment == "prod":
            # Default to production credentials
            url_env_var = "SUPABASE_URL"
            key_env_var = "SUPABASE_SERVICE_ROLE_KEY"
        else:
            raise ValueError("Invalid environment specified: " + environment)

        supabase_url = os.getenv(url_env_var)
        supabase_key = os.getenv(key_env_var)
        
        if not supabase_url or not supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set"
            )
        
        _supabase_client = create_client(supabase_url, supabase_key)
        logger.info("Supabase client initialized")
    
    return _supabase_client


def get_pinecone_client() -> Optional[Pinecone]:
    """
    Get or create a Pinecone client instance.
    
    Returns:
        Optional[Pinecone]: Pinecone client instance or None if API key not available
    """
    global _pinecone_client
    
    if _pinecone_client is None:
        environment = os.getenv("ENVIRONMENT", "local").lower()
        
        if environment in ["preprod", "local"]:
            key_env_var = "PINECONE_API_KEY_PREPROD"
        elif environment == "prod":
            key_env_var = "PINECONE_API_KEY"
        else:
            raise ValueError("Invalid environment specified: " + environment)
            
        pinecone_api_key = os.getenv(key_env_var)
        
        if not pinecone_api_key:
            logger.warning("PINECONE_API_KEY not found in environment variables")
            return None
        
        _pinecone_client = Pinecone(api_key=pinecone_api_key)
        logger.info("Pinecone client initialized")
    
    return _pinecone_client

def get_openrouter_client() -> Optional[OpenAI]:
    """
    Get or create an OpenAI client instance.
    
    Returns:
        Optional[OpenAI]: OpenAI client instance or None if API key not available
    """
    global _openrouter_client
    
    if _openrouter_client is None:
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        
        if not openrouter_api_key:
            logger.warning("OPENROUTER_API_KEY not found in environment variables")
            return None
        
        # Initialize the client with OpenRouter base URL
        _openrouter_client = OpenAI(
            api_key=openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                # Optional headers for OpenRouter leaderboard or attribution
                "HTTP-Referer": os.getenv("APP_URL", "http://localhost"),
                "X-Title": os.getenv("APP_NAME", "Wvelength Temporal"),
            }
        )
        logger.info("OpenRouter client initialized")
    
    return _openrouter_client

def get_async_openrouter_client() -> Optional[AsyncOpenAI]:
    """
    Get or create an async OpenAI client instance.
    
    Returns:
        Optional[AsyncOpenAI]: Async OpenAI client instance or None if API key not available
    """
    global _async_openrouter_client
    
    if _async_openrouter_client is None:
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        
        if not openrouter_api_key:
            logger.warning("OPENROUTER_API_KEY not found in environment variables")
            return None
        
        # Initialize the async client with OpenRouter base URL
        _async_openrouter_client = AsyncOpenAI(
            api_key=openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                # Optional headers for OpenRouter leaderboard or attribution
                "HTTP-Referer": os.getenv("APP_URL", "http://localhost"),
                "X-Title": os.getenv("APP_NAME", "Wvelength Temporal"),
            }
        )
        logger.info("Async OpenRouter client initialized")
    
    return _async_openrouter_client

def get_pinecone_index_name() -> str:
    """
    Get the Pinecone index name from environment variables based on the environment.
    
    Returns:
        str: Pinecone index name.
        
    Raises:
        ValueError: If an invalid environment is specified.
    """
    environment = os.getenv("ENVIRONMENT", "local").lower()
    
    if environment in ["preprod", "local"]:
        # Use pre-production index name, with 'test' as a fallback
        return os.getenv("PINECONE_INDEX_NAME_PREPROD", "test")
    elif environment == "prod":
        # Use production index name, with 'wave-matches' as a fallback
        return os.getenv("PINECONE_INDEX_NAME", "wave-matches")
    else:
        raise ValueError(f"Invalid ENVIRONMENT specified: '{environment}'")

def reset_clients():
    """
    Reset all client instances. Useful for testing or when credentials change.
    """
    global _supabase_client, _pinecone_client
    _supabase_client = None
    _pinecone_client = None
    logger.info("All client instances reset")