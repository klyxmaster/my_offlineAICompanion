import time
import ollama
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import PlainTextResponse, FileResponse
from pydantic import BaseModel
import uvicorn
import os
import sqlite3
import numpy as np
from sentence_transformers import SentenceTransformer

# Declare constants for the model names
CHAT_MODEL = 'wizard-vicuna-uncensored:13b'
EMBEDDING_MODEL = 'nomic-embed-text'  # For generating 384-dimensional embeddings
PERSONALITY_FILE = "personality.txt"  # The file containing the system prompt or personality
DB_FILE = "conversations.db"  # SQLite database file
VECTOR_DIM = 384  # Embedding dimensionality

# Initialize FastAPI app
app = FastAPI()

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins, or specify a domain.
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods.
    allow_headers=["*"],  # Allow all headers.
)

# Serve static files from the "static" directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize the embedding model globally
embedder = SentenceTransformer('all-MiniLM-L6-v2')

# Set up SQLite database
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Create a table for conversations and embeddings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT,
            response TEXT,
            embedding BLOB
        )
    ''')
    conn.commit()
    conn.close()

# Store conversation in SQLite
def store_conversation(prompt, response):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Generate an embedding for the conversation
    embedding = get_embedding(prompt + response)
    # Convert the embedding to a format that SQLite can store
    embedding_blob = np.array(embedding).tobytes()
    cursor.execute(
        "INSERT INTO conversations (prompt, response, embedding) VALUES (?, ?, ?)",
        (prompt, response, embedding_blob)
    )
    conn.commit()
    conn.close()

# Retrieve and compare similar conversations from SQLite
def get_similar_conversations(prompt):
    embedding = get_embedding(prompt)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, embedding FROM conversations")
    rows = cursor.fetchall()

    if not rows:
        return []
    
    similarities = []
    
    # Compare the query embedding to all stored embeddings
    for row in rows:
        conv_id, stored_embedding_blob = row
        stored_embedding = np.frombuffer(stored_embedding_blob, dtype=np.float32)
        
        # Calculate cosine similarity
        similarity = np.dot(embedding, stored_embedding) / (np.linalg.norm(embedding) * np.linalg.norm(stored_embedding))
        similarities.append((conv_id, similarity))
    
    # Sort by similarity and retrieve the top 5 most similar
    similarities.sort(key=lambda x: x[1], reverse=True)
    top_5_ids = [conv_id for conv_id, _ in similarities[:5]]
    
    # Fetch the corresponding conversation texts
    cursor.execute(f"SELECT id, prompt, response FROM conversations WHERE id IN ({','.join('?' for _ in top_5_ids)})", top_5_ids)
    similar_conversations = cursor.fetchall()
    
    conn.close()
    return similar_conversations

# Load the system prompt/personality from the file
def load_personality():
    try:
        with open(PERSONALITY_FILE, "r", encoding="utf-8") as file:
            return file.read().strip()
    except FileNotFoundError:
        return "Default system instructions or personality prompt."

# Generate embedding using the embedding model
def get_embedding(text):
    return embedder.encode(text)

# Define the PromptModel
class PromptModel(BaseModel):
    prompt: str  # Ensure the prompt field is a string

@app.post("/send_prompt/")
def send_prompt(data: PromptModel):
    prompt = data.prompt

    # Load personality/system prompt from file
    system_prompt = load_personality()

    # Add specific instructions to the system prompt dynamically
    system_prompt += "\nAlways address the user directly and respond in the second person."

    # Retrieve similar conversations
    similar_conversations = get_similar_conversations(prompt)

    # Add past conversation context if available
    past_convo_context = ""
    for conv_id, conv_prompt, conv_response in similar_conversations:
        past_convo = f"Past conversation {conv_id}: {conv_prompt} -> {conv_response}"
        past_convo_context += past_convo + "\n"

    if past_convo_context:
        system_prompt += f"\nHere are some past relevant conversations:\n{past_convo_context}"

    # Prepare the conversation
    convo = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': prompt}
    ]

    # Get the AI response using the model
    response = ollama.chat(CHAT_MODEL, convo)['message']['content']

    # Store the new conversation
    store_conversation(prompt, response)

    return PlainTextResponse(response)

# Serve the index.html file at the root URL
@app.get("/")
def read_root():
    return FileResponse('/static/index.html')

# Initialize the SQLite database
init_db()

# Start the FastAPI app
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
