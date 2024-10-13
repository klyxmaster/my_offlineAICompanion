import time
import ollama
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import PlainTextResponse, FileResponse
from pydantic import BaseModel
import uvicorn
import os
from annoy import AnnoyIndex
import numpy as np
from sentence_transformers import SentenceTransformer
import tempfile
import random

# Declare constants for the model names
CHAT_MODEL = 'wizard-vicuna-uncensored:13b'  # For generating text responses
EMBEDDING_MODEL = 'nomic-embed-text'  # For generating 384-dimensional embeddings
PERSONALITY_FILE = "personality.txt"  # The file containing the system prompt or personality
ANNOY_INDEX_FILE = os.path.join(tempfile.gettempdir(), "memory.ann")
VECTOR_DIM = 384  # Annoy index dimensionality

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

# Initialize Annoy index
annoy_index = AnnoyIndex(VECTOR_DIM, 'angular')

# Check if Annoy index exists and load it if present
if os.path.exists(ANNOY_INDEX_FILE):
    try:
        annoy_index.load(ANNOY_INDEX_FILE)
        print(f"Loaded Annoy index from {ANNOY_INDEX_FILE}")
    except Exception as e:
        print(f"Error loading Annoy index: {e}")
else:
    print("Annoy index file not found.")

# Initialize the embedding model globally
embedder = SentenceTransformer('all-MiniLM-L6-v2')  # You can replace this with the correct model you need

# Define the PromptModel
class PromptModel(BaseModel):
    prompt: str  # Ensure the prompt field is a string

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

# Store conversation and update Annoy index
def store_conversation(prompt, response):
    global annoy_index

    # Generate an embedding for the conversation
    embedding = get_embedding(prompt + response)

    # Create a temporary Annoy index to rebuild
    temp_annoy_index = AnnoyIndex(VECTOR_DIM, 'angular')

    # Copy the existing items from the loaded Annoy index to the new one
    for i in range(annoy_index.get_n_items()):
        vector = annoy_index.get_item_vector(i)
        temp_annoy_index.add_item(i, vector)

    # Add the new embedding to the new Annoy index
    temp_annoy_index.add_item(temp_annoy_index.get_n_items(), embedding)

    # Build the new index with 10 trees
    temp_annoy_index.build(10)

    try:
        # Save the new index to disk
        temp_annoy_index.save(ANNOY_INDEX_FILE)
        print(f"Annoy index saved at {ANNOY_INDEX_FILE}")
    except OSError as e:
        print(f"Error saving Annoy index: {e}")

    # Replace the old in-memory index with the newly built one
    annoy_index = temp_annoy_index
    temp_annoy_index.unload()  # Explicitly release memory

# Retrieve similar conversations
def get_similar_conversations(prompt):
    embedding = get_embedding(prompt)

    if annoy_index.get_n_items() == 0:
        return []

    # Retrieve the top 5 most similar conversations
    similar_indices = annoy_index.get_nns_by_vector(embedding, 5, include_distances=False)
    return similar_indices

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
    for i in similar_conversations:
        past_convo = f"Past conversation {i}: [Logic to fetch conversation data]"
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

# Start the FastAPI app
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
