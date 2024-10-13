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
import colorlog
from sentence_transformers import SentenceTransformer
import tempfile

# Declare constants for the model names
CHAT_MODEL = 'dolphin-llama3:8b-256k'  # For generating text responses
EMBEDDING_MODEL = 'nomic-embed-text'  # For generating 384-dimensional embeddings
PERSONALITY_FILE = "personality.txt"  # The file containing the system prompt or personality
ANNOY_INDEX_FILE = "memory.ann"
VECTOR_DIM = 384  # Annoy index dimensionality
import tempfile

# Use the system's temporary directory for the Annoy index file
ANNOY_INDEX_FILE = os.path.join(tempfile.gettempdir(), "memory.ann")


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
    annoy_index.load(ANNOY_INDEX_FILE)

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

# Dummy function to simulate the chat model interaction (using llama3)
def chat_with_model(system_prompt, user_prompt):
    # This is where you'd integrate with the actual AI model, such as llama3.
    # For now, it returns a dummy response.
    return f"System says: {system_prompt}. You said: {user_prompt}"

# Ensure that the ANNOY_INDEX_FILE path is absolute and valid
ANNOY_INDEX_FILE = os.path.join(os.getcwd(), "memory.ann")

def store_conversation(prompt, response):
    # Generate an embedding for the prompt (or the conversation)
    embedding = get_embedding(prompt)

    global annoy_index

    # Create a fresh Annoy index to rebuild
    temp_annoy_index = AnnoyIndex(VECTOR_DIM, 'angular')

    # Copy the existing items from the loaded Annoy index to the new one
    if os.path.exists(ANNOY_INDEX_FILE):
        for i in range(annoy_index.get_n_items()):
            vector = annoy_index.get_item_vector(i)
            temp_annoy_index.add_item(i, vector)

    # Now add the new embedding to the new Annoy index
    temp_annoy_index.add_item(temp_annoy_index.get_n_items(), embedding)

    # Build the new index with 10 trees (adjust as needed for performance/accuracy)
    temp_annoy_index.build(10)

    try:
        # Save the new index to the disk using an absolute path
        temp_annoy_index.save(ANNOY_INDEX_FILE)
        print(f"Annoy index saved at {ANNOY_INDEX_FILE}")
    except OSError as e:
        print(f"Error saving Annoy index: {e}")
        raise

    # Replace the old in-memory index with the newly built one
    annoy_index = temp_annoy_index
    # Explicitly release the memory for the old index
    temp_annoy_index.unload()


# Retrieve similar conversations
def get_similar_conversations(prompt):
    # Generate embedding for the input prompt
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
    system_prompt += "\nRemember: Always address the user as 'you' and respond in the second person. Never switch roles. You are the assistant, and the user is always addressed directly."

    # Retrieve similar conversations (this should return IDs or indices of similar items)
    similar_conversations = get_similar_conversations(prompt)

    # Fetch the actual conversation data for the similar conversations (assuming conversation_data is stored somewhere)
    past_convo_context = ""
    for i in similar_conversations:
        # Retrieve the actual conversation from wherever you store the conversation history
        past_convo = f"Past conversation {i}: [Your logic to fetch conversation data goes here]"
        past_convo_context += past_convo + "\n"

    # Include the past conversation context in the system prompt or as part of the user prompt
    if past_convo_context:
        system_prompt += f"\nHere are some past relevant conversations:\n{past_convo_context}"

    # Prepare the conversation with the system prompt and the user's input
    convo = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': prompt}
    ]

    # Get the AI response using the model, passing the conversation with roles
    response = ollama.chat(CHAT_MODEL, convo)['message']['content']

    # Save the raw AI response to a text file
    with open('response.txt', 'w') as file:
        file.write(response)

    # Store the new conversation (user prompt and response)
    store_conversation(prompt, response)

    return PlainTextResponse(response)


# Serve the index.html file at the root URL
@app.get("/")
def read_root():
    return FileResponse('/static/index.html')

# Start the FastAPI app
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
