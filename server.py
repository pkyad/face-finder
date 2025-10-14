#!/usr/bin/env python3
"""
FastAPI Face Recognition Server with Streaming Results
Streams matching filenames as they are found in real-time.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import face_recognition
import os
import asyncio
from typing import List, Dict
from pathlib import Path

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class FaceSearcher:
    def __init__(self, tolerance: float = 0.6, min_confidence: float = 55.0):
        self.tolerance = tolerance
        self.min_confidence = min_confidence
        self.reference_encoding = None
        self.reference_path = None
    
    def load_reference_face(self, image_path: str) -> bool:
        """Load the reference face from image"""
        if not os.path.exists(image_path):
            return False
        
        try:
            reference_image = face_recognition.load_image_file(image_path)
            face_encodings = face_recognition.face_encodings(reference_image)
            
            if len(face_encodings) == 0:
                return False
            
            self.reference_encoding = face_encodings[0]
            self.reference_path = image_path
            return True
        except Exception:
            return False
    
    async def stream_search(self, album_folder: str):
        """
        Generator that yields matches as they are found.
        Streams filename and confidence as soon as a match is detected.
        """
        if self.reference_encoding is None:
            yield "error: No reference face loaded\n\n"
            return
        
        if not os.path.exists(album_folder):
            yield f"error: Album folder not found: {album_folder}\n\n"
            return
        
        # Get all JPG files
        jpg_files = []
        for filename in os.listdir(album_folder):
            if filename.lower().endswith('.jpg'):
                jpg_files.append(os.path.join(album_folder, filename))
        
        if not jpg_files:
            yield f"error: No JPG files found in {album_folder}\n\n"
            return
        
        yield f"data: Searching in {len(jpg_files)} images...\n\n"
        await asyncio.sleep(0.1)
        
        match_count = 0
        
        for image_path in jpg_files:
            filename = os.path.basename(image_path)
            
            try:
                # Load image and find faces
                image = face_recognition.load_image_file(image_path)
                face_locations = face_recognition.face_locations(image)
                face_encodings = face_recognition.face_encodings(image, face_locations)
                
                # Check each face against reference
                for i, face_encoding in enumerate(face_encodings):
                    face_distance = face_recognition.face_distance(
                        [self.reference_encoding], face_encoding
                    )[0]
                    confidence = (1 - face_distance) * 100
                    
                    # Stream match immediately
                    if face_distance <= self.tolerance and confidence >= self.min_confidence:
                        match_count += 1
                        result = f"✅ MATCH {match_count}: {filename} | Confidence: {confidence:.1f}%"
                        yield f"data: {result}\n\n"
                        await asyncio.sleep(0.05)
                
            except Exception as e:
                error_msg = f"⚠️ Error processing {filename}: {str(e)}"
                yield f"data: {error_msg}\n\n"
                continue
        
        # Final summary
        summary = f"\n🎯 Search Complete! Total matches: {match_count}"
        yield f"data: {summary}\n\n"


# Initialize searcher
searcher = FaceSearcher()

@app.on_event("startup")
async def startup_event():
    """Load reference face on startup"""
    reference_path = "sample.png"
    if os.path.exists(reference_path):
        if searcher.load_reference_face(reference_path):
            print(f"✅ Reference face loaded from {reference_path}")
        else:
            print(f"❌ Failed to load reference face from {reference_path}")
    else:
        print(f"⚠️ Reference image not found: {reference_path}")


@app.get("/search")
async def search_faces():
    """
    Stream face recognition results as matches are found.
    Streams results in Server-Sent Events (SSE) format.
    """
    if searcher.reference_encoding is None:
        raise HTTPException(
            status_code=400,
            detail="Reference face not loaded. Ensure sample.png exists and contains a face."
        )
    
    album_folder = "album_resized"
    
    return StreamingResponse(
        searcher.stream_search(album_folder),
        media_type="text/event-stream"
    )


@app.get("/search/{album_name}")
async def search_faces_custom_album(album_name: str):
    """
    Stream face recognition results from a custom album folder.
    
    Usage: /search/my_album_folder
    """
    if searcher.reference_encoding is None:
        raise HTTPException(
            status_code=400,
            detail="Reference face not loaded. Ensure sample.png exists and contains a face."
        )
    
    album_folder = album_name
    
    return StreamingResponse(
        searcher.stream_search(album_folder),
        media_type="text/event-stream"
    )


@app.get("/images/{album_name}/{image_name}")
async def get_image(album_name: str, image_name: str):
    """
    Serve static images from album folders.
    
    Usage: /images/album_resized/image.jpg
    """
    # Prevent directory traversal attacks
    if ".." in album_name or ".." in image_name:
        raise HTTPException(status_code=400, detail="Invalid path")
    
    image_path = os.path.join(album_name, image_name)
    
    # Verify the file exists and is in the correct directory
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail=f"Image not found: {image_path}")
    
    # Verify it's actually in the requested album folder
    real_path = os.path.realpath(image_path)
    real_album = os.path.realpath(album_name)
    
    if not real_path.startswith(real_album):
        raise HTTPException(status_code=400, detail="Invalid path")
    
    # Verify it's an image file
    if not image_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    return FileResponse(image_path)


@app.get("/")
async def root():
    """API information"""
    return {
        "name": "Face Recognition Streaming Server",
        "endpoints": {
            "/search": "Search in default 'album_resized' folder",
            "/search/{album_name}": "Search in custom album folder",
            "/images/{album_name}/{image_name}": "Serve static images"
        },
        "usage": "Access the endpoints in your browser or use curl",
        "example_curl": "curl http://localhost:8000/search",
        "example_image": "http://localhost:8000/images/album_resized/photo.jpg"
    }


@app.get("/status")
async def status():
    """Check if reference face is loaded"""
    return {
        "reference_loaded": searcher.reference_encoding is not None,
        "reference_path": searcher.reference_path,
        "tolerance": searcher.tolerance,
        "min_confidence": searcher.min_confidence
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)