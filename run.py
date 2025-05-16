from app import app, socketio
from dotenv import load_dotenv
import os
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])
logger = logging.getLogger("LMS-RAG-Chatbot")

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Get port from environment or use default
    port = int(os.getenv('PORT', 8080))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # Rebuild vector store to ensure latest data
    try:
        logger.info("Rebuilding vector store from latest MongoDB data...")
        from lms_rag import build_vector_store
        vector_store = build_vector_store()
        if vector_store:
            logger.info("Vector store rebuilt successfully!")
        else:
            logger.warning("Failed to rebuild vector store. Chat functionality may be limited.")
    except Exception as e:
        logger.error(f"Error rebuilding vector store: {e}")
        logger.warning("Continuing with potentially outdated vector store...")
    
    # Run the app
    logger.info(f"Starting LMS RAG Chatbot on port {port} (debug: {debug})")
    socketio.run(app, debug=debug, host='0.0.0.0', port=port) 